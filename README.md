# Project Plan Scrutinizer

A deterministic project audit application for reviewing project plans. This is **not** a chatbot.

The app accepts a project plan as pasted text or an uploaded document, runs it through a hybrid audit pipeline, and returns a structured report with scores, findings, recommendations, saved history, exports, privacy controls, and optional team workspaces.

## What it does

- Ingests `PDF`, `DOCX`, `TXT`, and `MD` project plans
- Extracts core sections such as objectives, scope, deliverables, timeline, resources, risks, governance, assumptions, constraints, and budget
- Runs a deterministic rule engine for structure, consistency, timeline, risk, resource, and governance checks
- Optionally adds AI insights for softer quality issues when an OpenAI key is configured
- Scores the plan deterministically from rule findings only
- Saves report history with filtering, comparison, export, and reopen support
- Supports user accounts, free usage, credit packs, subscriptions, privacy/data export, and shared workspaces

## Key product behavior

- **Deterministic-first**: the rule engine is the primary source of truth
- **Optional AI layer**: AI insights are supplementary and do not affect scoring
- **True deterministic mode**: when AI is disabled, the app does not use LLM fallback for section extraction
- **Structured output**: results are rendered as an audit report, not a conversation
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
    dashboard_page.py
    findings_display.py
    history_page.py
    privacy_page.py
    pricing_page.py
    recommendations_display.py
    score_display.py
    top_issues.py
    workspace_page.py
  llm_engine/
    insights.py
  payments/
    checkout.py
    plans.py
    stripe_client.py
    webhook.py
  pipeline/
    input_layer.py
    orchestrator.py
    preprocessor.py
    report_generator.py
    scoring_engine.py
    section_extractor.py
  rule_engine/
    runner.py
    models.py
    *_rules.py
  utils/
    llm_client.py
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

- `OPENAI_API_KEY` is **optional**
- Stripe variables are **optional** for local non-payment testing
- The app works without Stripe and without OpenAI

Example minimal local `.env`:

```env
# Optional: enables AI insights on top of deterministic findings
# OPENAI_API_KEY=your-key-here
# OPENAI_MODEL=gpt-4o

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
