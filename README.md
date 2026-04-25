# Project Plan Scrutinizer

A deterministic project audit application for reviewing project plans, with optional AI features for drafting and revising plans.

The app accepts a project plan as pasted text, an uploaded document, **or a free-form prompt** (which the AI drafts into a plan). It runs the plan through a hybrid audit pipeline and returns a structured report with scores, findings, recommendations, saved history, exports, privacy controls, and optional team workspaces. A scoped chat assistant and a fixed set of "Quick Actions" let you ask about findings or revise individual sections — but the rule engine remains the **only** source of scoring.

## What it does

- Ingests `PDF`, `DOCX`, `TXT`, and `MD` project plans
- **Generates draft plans from a free-form prompt** (optional, requires an LLM key)
- Extracts core sections such as objectives, scope, deliverables, timeline, resources, risks, governance, assumptions, constraints, and budget
- Runs a deterministic rule engine for structure, consistency, timeline, risk, resource, and governance checks
- Optionally adds AI insights for softer quality issues when an LLM provider is configured
- **Plan-aware chat assistant**: ask questions about the loaded plan or its findings (read-only)
- **Quick Actions**: rewrite a section, add a section, or regenerate the timeline — every change is shown as a diff and you accept or reject before anything is overwritten
- Scores the plan deterministically from rule findings only — AI never affects scores
- Saves report history with filtering, comparison, export, and reopen support
- Supports user accounts, free usage, credit packs, subscriptions, privacy/data export, and shared workspaces

## Key product behavior

- **Deterministic-first**: the rule engine is the only source of scoring
- **Optional AI layer**: AI features (insights, generation, chat, Quick Actions) are supplementary and do not affect scoring
- **True deterministic mode**: when AI is disabled, the app does not use LLM fallback for section extraction or anything else
- **Structured output**: results are rendered as an audit report; chat is scoped to the loaded plan
- **No silent edits**: every AI-proposed change to the plan goes through an explicit accept/reject diff
- **Bounded surface**: chat verbs are a fixed list (rewrite_section, add_section, regenerate_timeline). The assistant cannot run code or external tools.
- **Per-user token budget**: every LLM call is metered against a monthly cap to control cost
- **Privacy-conscious defaults**: the app stores report metadata and saved report output, but does not intentionally retain raw uploaded document content by default

## Main features

### Analysis

- Overall score and grade
- Weighted category breakdown
- Top issues
- Detailed rule findings by category
- Prioritised recommendations
- Optional AI insights

### Account and usage

- Email-based registration and login
- Free tier with monthly usage limits
- Credit-pack and subscription support
- Profile details such as display name and organisation
- Account dashboard with totals, average score, best score, and recent analyses

### History and exports

- Saved analysis history
- Search, filter, and sort
- Reopen saved reports
- Compare two saved reports side by side
- Export reports as `Markdown` and `PDF`
- Export history as `CSV`

### Privacy and workspaces

- Export account data as `JSON`
- Delete account and local saved data
- Create and join shared workspaces with join codes
- Save analyses either privately or into a shared workspace

## Architecture

```text
app.py
app/
  auth/
    db.py
    models.py
    service.py
    session.py
  components/
    auth_page.py
    chat_panel.py            # plan-aware read-only chat
    dashboard_page.py
    findings_display.py
    history_page.py
    privacy_page.py
    pricing_page.py
    quick_actions.py         # rewrite/add/regenerate verbs
    recommendations_display.py
    score_display.py
    top_issues.py
    workspace_page.py
  llm/
    openrouter.py            # HTTP client (OpenRouter primary, OpenAI fallback)
    budget.py                # per-user token budget enforcement
    chat_service.py          # read-only chat turn handler
    verbs.py                 # write-action verbs (rewrite, add, regenerate)
    prompts/
      generate_plan.py
      chat_assistant.py
      write_verbs.py
  llm_engine/
    insights.py              # AI Insights layer (uses app.llm.openrouter)
  payments/
    checkout.py
    plans.py
    stripe_client.py
    webhook.py
  pipeline/
    input_layer.py
    orchestrator.py
    plan_generator.py        # prompt → draft plan markdown
    preprocessor.py
    report_generator.py
    scoring_engine.py
    section_extractor.py
  rule_engine/
    runner.py
    models.py
    *_rules.py
  utils/
    llm_client.py            # legacy shim — calls into app/llm/openrouter
    pdf_export.py
webhook_server.py
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file from `.env.example`.

Important notes:

- LLM features (AI Insights, plan generation, chat, Quick Actions) require either `OPENROUTER_API_KEY` (preferred) or `OPENAI_API_KEY`. Both are **optional** — the deterministic audit works without them.
- Stripe variables are **optional** for local non-payment testing
- Per-user monthly token budgets default to Free 20k / Credits 200k / Pro 2M, overridable via env

Example minimal local `.env`:

```env
# Optional: enables AI features (insights, plan generation, chat, Quick Actions)
# OPENROUTER_API_KEY=sk-or-v1-...
# OPENROUTER_MODEL=anthropic/claude-haiku-4-5

APP_URL=http://localhost:3000
WEBHOOK_PORT=4242
```

### 3. Run the app

```bash
python -m streamlit run app.py --server.port 3000
```

Open [http://localhost:3000](http://localhost:3000).

### 4. Optional Stripe webhook server

If you want to test payments later:

```bash
python webhook_server.py
```

## Typical local workflow

1. Start the Streamlit app
2. Register a new account
3. Stay on the free tier for basic testing
4. Paste a project plan or upload a file
5. Run analysis
6. Review the report, exports, history, and dashboard

## Scoring model

Scores are deterministic and derived from rule findings only.

Category weights:

| Category | Weight |
|---|---:|
| Structure | 25% |
| Consistency | 15% |
| Timeline | 20% |
| Risk | 20% |
| Resource | 12% |
| Governance | 8% |

Severity penalties:

- `critical`: 3.0
- `high`: 1.5
- `medium`: 0.7
- `low`: 0.3
- `info`: 0.0

## Current limitations

- The app is strong for local and prototype use, but it is not yet a formally certified compliance product
- Stripe setup requires valid keys and webhook configuration
- Workspace support is focused on shared history, not real-time collaboration
- PDF export is intentionally lightweight and text-based

## Development notes

- Test suite:

```bash
python -m pytest
```

- The local SQLite database is stored under `data/` and is gitignored
- `APP_REVIEW.md` contains an internal product review and enhancement notes
