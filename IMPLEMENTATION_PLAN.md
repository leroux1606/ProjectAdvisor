# Implementation Plan — Chat Assistant + Plan Generator

**Date:** 2026-04-25
**Status:** Proposed — awaiting approval before any code is written.

## 1. Goals & Non-Goals

### Goals

1. **Plan Generator** — user enters a free-form prompt; system produces a draft project plan, then immediately runs it through the existing audit pipeline so the user sees the plan *and* its score in one flow.
2. **Plan-Aware Chat Assistant** — once a plan is loaded (uploaded/pasted/generated), the user can chat about it: ask questions, request rewrites of specific sections, ask "explain finding #4", regenerate the timeline, etc.
3. **OpenRouter as the LLM gateway** — single key, model selectable, replaces direct OpenAI dependency for the new features. Existing AI Insights layer also moves to OpenRouter (one client to maintain).

### Non-Goals

- The chat is **not** a free agent that can run arbitrary tools. Verbs are a fixed, scoped list.
- LLM output **never** affects scoring. Scoring stays 100% rule-based. This is a load-bearing product invariant.
- No real-time collaboration, no streaming-token UX in v1 (Streamlit limitation; can add later).
- No new payment SKUs in v1 — we use the existing credit / Pro tier system but introduce per-user **token budgets** to control LLM cost.

## 2. Architectural Shape

```
                    ┌─────────────────────────────────────────────────┐
                    │ Streamlit UI                                    │
                    │  • Plan input (existing)                        │
                    │  • NEW: "Generate from prompt" tab              │
                    │  • NEW: Chat panel (after plan is loaded)       │
                    └─────────────────────┬───────────────────────────┘
                                          │
                  ┌───────────────────────┼─────────────────────────┐
                  │                       │                         │
        ┌─────────▼─────────┐  ┌──────────▼──────────┐  ┌───────────▼──────────┐
        │ run_pipeline()    │  │ generate_plan()     │  │ chat_turn()          │
        │ (existing)        │  │ NEW                 │  │ NEW                  │
        └─────────┬─────────┘  └──────────┬──────────┘  └───────────┬──────────┘
                  │                       │                         │
                  └───────────────────────┼─────────────────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │ app/llm/openrouter.py  │ NEW — single client
                              │  • call_chat()         │
                              │  • call_json()         │
                              │  • token accounting    │
                              └───────────┬────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │ openrouter.ai/api/v1   │
                              └────────────────────────┘
```

Key principle: **chat and generation are services that produce text; the audit pipeline is the single source of truth for scoring.** Generated plans are fed *back through* `run_pipeline()` unchanged — no special path.

## 3. Pre-Work (Mandatory Before Building)

These are existing High-severity items from `APP_REVIEW.md` that *will get worse* if we add LLM features on top of them:

| # | Item | Why blocking |
|---|---|---|
| 1 | Escape `unsafe_allow_html=True` content (`app.py`, `findings_display.py`, `top_issues.py`, `recommendations_display.py`, `dashboard_page.py`) | LLM output rendered as HTML = XSS vector. Must fix before any model output reaches the UI. |
| 2 | Move `consume_analysis()` to *after* successful pipeline run | Plan generation is a 2-step LLM flow. Failure mid-flow must not consume credits. |
| 3 | Stripe webhook idempotency | Independent, but if we touch quotas/credits we should not leave this open. |

**Estimated effort:** 1–2 days. Recommend a single PR titled "harden existing surface before adding LLM features."

## 4. File-by-File Changes

### 4.1 New module: `app/llm/` (replaces `app/utils/llm_client.py` and `app/llm_engine/`)

```
app/llm/
  __init__.py
  openrouter.py        # client (chat + json modes, retries, timeouts)
  budget.py            # per-user token accounting + quota check
  prompts/
    __init__.py
    generate_plan.py   # system + user prompt builders for plan generation
    chat_assistant.py  # system prompt + tool descriptions for chat
    insights.py        # moved from app/llm_engine/insights.py
  tools.py             # the fixed verb list (see §4.4)
  schemas.py           # Pydantic models for structured responses
```

**`openrouter.py` interface:**

```python
def call_chat(messages, *, model=None, temperature=0.0, max_tokens=2048,
              user_id: int, purpose: str) -> ChatResult: ...

def call_json(messages, *, schema, model=None, user_id: int, purpose: str) -> dict: ...
```

- Reads `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (default: `anthropic/claude-sonnet-4-6` or similar; configurable).
- Uses `requests` against `https://openrouter.ai/api/v1/chat/completions` to avoid pulling in another SDK.
- Sends `HTTP-Referer` and `X-Title` headers (OpenRouter recommends these for app attribution).
- Wraps every call with budget check (`budget.assert_can_spend(user_id, est_tokens)`) and after-call accounting (`budget.record_spend(...)`).
- `purpose` is recorded so we can break down spend by feature: `generate_plan`, `chat_turn`, `insights`, `section_extract`.

### 4.2 Replace `app/utils/llm_client.py`

- Keep file as a **thin shim** that calls into `app/llm/openrouter.py` so existing `app/llm_engine/insights.py` and `app/pipeline/section_extractor.py` continue to work without code churn during the transition.
- After everything migrates, delete the shim.

### 4.3 New: Plan Generator

**File:** `app/pipeline/plan_generator.py`

```python
def generate_plan(prompt: str, project_type: str, user_id: int) -> GeneratedPlan:
    """
    Returns a GeneratedPlan with:
      - text: str             # the full plan markdown
      - sections: dict        # parsed sections (objectives, scope, ...)
      - model: str            # which model produced it
      - tokens_used: int
    Raises BudgetExceeded, GenerationError.
    """
```

- Prompt builder lives in `app/llm/prompts/generate_plan.py`.
- The prompt instructs the model to produce a plan covering the **same sections the rule engine looks for** (`app/pipeline/section_extractor.py` knows the canonical list). This dramatically improves audit scores on first generation.
- Returns markdown text — **does not pre-fill scores or findings**. The plan flows through `run_pipeline()` like any other input.

**UI integration (`app.py`):**
- New tab in the "Submit Project Plan" expander: `📝 Paste Text | 📁 Upload File | ✨ Generate from Prompt`.
- On generate: call `generate_plan()`, populate the text area with the result, *then* the user clicks "Analyze" as today. Two clicks, not one — gives the user a chance to edit before audit.

### 4.4 New: Chat Assistant

**File:** `app/components/chat_panel.py`

UI:
- Renders below the report when a report is loaded in session.
- Uses `st.chat_message` and `st.chat_input` (built-in Streamlit primitives — escapes content for us).
- Persists per-report chat history in `st.session_state["chat_history"][report_id]`.

**File:** `app/llm/chat_service.py`

```python
def chat_turn(report: AuditReport, plan_text: str,
              history: list[Message], user_message: str,
              user_id: int) -> ChatTurnResult:
    """
    Returns:
      - reply_text: str
      - action: Optional[ChatAction]    # if model invoked a verb
      - updated_plan: Optional[str]     # if a verb modified the plan
      - tokens_used: int
    """
```

**Fixed verb list** (`app/llm/tools.py`):

| Verb | Effect | Re-runs audit? |
|---|---|---|
| `explain_finding(finding_id)` | Returns a plain-language explanation of a rule finding. | No |
| `rewrite_section(section_name, instructions)` | Returns a rewritten section. User reviews diff and accepts/rejects. | Yes, on accept |
| `add_section(section_name, instructions)` | Drafts a new section to append. | Yes, on accept |
| `regenerate_timeline(constraints)` | Rewrites the timeline section under new constraints. | Yes, on accept |
| `summarize_plan()` | Returns a 1-paragraph executive summary. | No |
| `answer_question(question)` | RAG-style Q&A over plan + findings. Default fallback. | No |

The verb list is enforced server-side: the chat service uses tool-calling (OpenRouter passes through to the underlying model's tool API for compatible models) **or** structured JSON output where the model picks a verb. We never `eval` model output or run shell commands.

### 4.5 Database changes (`app/auth/db.py`)

New tables (added in `init_db()` with `CREATE TABLE IF NOT EXISTS`):

```sql
CREATE TABLE IF NOT EXISTS llm_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    purpose         TEXT    NOT NULL,    -- 'generate_plan' | 'chat_turn' | 'insights' | ...
    model           TEXT    NOT NULL,
    prompt_tokens   INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_micro_usd  INTEGER,             -- null if cost not known
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    analysis_run_id INTEGER REFERENCES analysis_runs(id),
    role            TEXT    NOT NULL,    -- 'user' | 'assistant' | 'system'
    content         TEXT    NOT NULL,
    action_json     TEXT,                -- if a verb was invoked
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

Plus add to `users`:
- `monthly_token_budget INTEGER DEFAULT 50000` (configurable per tier)
- `monthly_tokens_used INTEGER DEFAULT 0` (resets on `usage_reset_date` like `monthly_usage`)

### 4.6 Settings & env

**`.env.example`** — add:
```
# OpenRouter (replaces OPENAI_API_KEY for new features)
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-sonnet-4-6
OPENROUTER_APP_URL=http://localhost:3000
OPENROUTER_APP_NAME=Project Plan Scrutinizer

# Token budgets (override defaults baked into code)
TOKEN_BUDGET_FREE=20000
TOKEN_BUDGET_CREDITS=200000
TOKEN_BUDGET_PRO=2000000
```

Keep `OPENAI_API_KEY` working for one release as a fallback so existing users aren't broken.

### 4.7 Sidebar settings (`app.py`)

- "AI provider: OpenRouter ✓ / OpenAI (legacy)" — auto-detected from env.
- "Model" dropdown — populated from a small allow-list (`anthropic/claude-sonnet-4-6`, `anthropic/claude-haiku-4-5`, `openai/gpt-4o`, `meta-llama/llama-3.1-70b-instruct`, etc.). Stored per-user.
- "Tokens used this month: X / Y" with a progress bar.

## 5. Phasing (recommended order)

Each phase is a separate PR. Each is independently shippable.

### Phase 0 — Pre-work (1–2 days)
- Fix HTML escaping across the listed files.
- Move `consume_analysis()` to post-success, with rollback path.
- Stripe webhook idempotency.

### Phase 1 — OpenRouter migration (1 day)
- Add `app/llm/openrouter.py`.
- Make `app/utils/llm_client.py` a shim.
- Add `llm_usage` table and basic accounting.
- Existing AI Insights now run via OpenRouter. No user-visible change.

### Phase 2 — Plan Generator (2–3 days)
- `app/pipeline/plan_generator.py` + prompts.
- New "Generate from Prompt" tab in the input expander.
- Token budget enforcement.
- Tests: prompt → plan → audit produces valid report; budget enforcement blocks over-quota users.

### Phase 3 — Chat Assistant: read-only verbs (3–4 days)
- `chat_panel.py`, `chat_service.py`, `tools.py` for `explain_finding`, `summarize_plan`, `answer_question` only.
- Persistence in `chat_messages`.
- Tests: each verb returns expected shape; injection attempts in user input don't change the system prompt.

### Phase 4 — Chat Assistant: write verbs (3–4 days)
- Add `rewrite_section`, `add_section`, `regenerate_timeline`.
- Diff UI: model proposes change → user sees side-by-side diff → accept/reject.
- On accept: write back to plan text, re-run audit, store new `analysis_run`.
- Tests: rejection leaves state untouched; acceptance produces a new audit row.

### Phase 5 — Polish (2 days)
- Per-tier token budgets configurable.
- Usage breakdown by `purpose` in the dashboard.
- Audit log of chat actions.
- Remove the `OPENAI_API_KEY` shim.

**Total estimate:** ~12–16 working days for one developer.

## 6. Testing Strategy

- **Unit:** `app/llm/openrouter.py` with HTTP mocked via `responses` or `pytest-httpx`.
- **Unit:** Each verb in `tools.py` with a stubbed model that returns canned responses.
- **Integration:** `generate_plan()` → `run_pipeline()` end-to-end with a recorded fixture response. Asserts the generated plan scores above a floor (sanity check on prompt quality).
- **Security:** Prompt-injection cases — user message containing `Ignore prior instructions...`, malicious markdown with HTML, and rendered output is checked for proper escaping in the chat panel.
- **Budget:** Going over budget raises `BudgetExceeded`; the user sees a friendly message, no API call is made.

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM cost runs away on a single user | Hard per-user monthly token budget, enforced *before* the API call (estimated tokens) and reconciled after. |
| Prompt injection via plan content / user chat | All system prompts are constants; user content is never concatenated into the system prompt. Tool calls are validated against the fixed verb schema. |
| Generated plans game the rule engine | Possible, but acceptable — the engine is public-by-nature. Mitigation: track score distribution of generated vs. uploaded plans; if generated consistently scores higher we'll know the prompt is overfit. |
| OpenRouter outage | Graceful degradation: chat/generation features show "AI temporarily unavailable"; deterministic audit continues to work. |
| Streaming UX expectation | Streamlit doesn't stream tokens cleanly. v1 ships with a spinner; if users push back, switch chat to a small `st.empty()` polling loop. |
| Scope creep into "AI does my whole project" | The fixed verb list is the contract. Adding a verb requires a PR; we don't ship a free-form `execute(...)` tool. |

## 8. Open Questions

1. **Default model.** Claude Sonnet 4.6 is the strongest balance of cost/quality for project text. Confirm before locking in.
2. **Free tier on AI features.** Should free users get *any* generations / chat turns, or is it Pro-only? My recommendation: 1 plan generation + 5 chat turns/month free, to drive conversion.
3. **Workspace-shared chat.** When a plan is in a workspace, do other members see the chat? Recommend: no in v1 (privacy default) — opt-in toggle in v2.
4. **Streaming.** Live in v2 unless you want it day one.
5. **Prompt versioning.** As we tune `generate_plan` prompts, do we version them and record which version produced which plan? Recommend: yes, store `prompt_version` in `analysis_runs`.

## 9. What I Need from You Before Coding

- ✅ / ❌ on each phase ordering (especially Phase 0 — it's the unglamorous one).
- Decision on Q2 (free-tier AI access).
- Decision on default model (Q1).
- Confirmation that token budgets at the suggested levels are acceptable, or alternative numbers.
- Whether you want this on a feature branch (`feat/ai-assistant`) merged at the end, or phase-by-phase to `main`.

