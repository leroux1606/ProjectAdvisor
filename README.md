# Project Plan Scrutinizer

A deterministic project audit tool — not a chatbot.

Ingests a project plan (PDF, DOCX, TXT, or pasted text) and produces a structured audit report with scores, findings, and prioritised recommendations aligned with **PRINCE2** and **PMBOK** standards.

---

## Architecture

```
app.py                          ← Streamlit UI entry point
app/
  pipeline/
    input_layer.py              ← File/text ingestion
    preprocessor.py             ← Text cleaning & normalisation
    section_extractor.py        ← LLM-based section extraction (JSON output)
    orchestrator.py             ← Pipeline runner
    scoring_engine.py           ← Deterministic score computation
    report_generator.py         ← Structured report assembly
  analysis/
    models.py                   ← Pydantic output models
    base.py                     ← Shared prompt utilities
    structure_analysis.py       ← Section completeness
    consistency_analysis.py     ← Cross-section contradiction detection
    timeline_analysis.py        ← Schedule realism & dependency checks
    risk_analysis.py            ← Risk register evaluation
    resource_analysis.py        ← Allocation & role gap detection
    governance_analysis.py      ← Oversight & change control
  components/
    score_display.py            ← Score gauge & breakdown
    findings_display.py         ← Grouped findings with severity badges
    recommendations_display.py  ← Prioritised action list
    top_issues.py               ← Summary top-5 issues
  utils/
    llm_client.py               ← OpenAI wrapper (temperature=0 enforced)
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

`.env` contents:
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

### 3. Run

```bash
streamlit run app.py
```

The app runs on **http://localhost:3000** (or the port Streamlit assigns).

---

## Usage

1. Open the app in your browser
2. Paste a project plan **or** upload a PDF / DOCX / TXT / MD file
3. Click **Analyse Project Plan**
4. Review the structured audit report:
   - **Overall Score** (1–10) with grade
   - **Score Breakdown** by category
   - **Top Issues** summary
   - **Detailed Findings** grouped by category (expandable)
   - **Prioritised Recommendations**

---

## Design Principles

- **No chatbot** — all outputs are structured JSON internally, rendered as a report
- **Deterministic** — LLM temperature is fixed at 0.0 for all analysis calls
- **Modular** — each analysis stage is an independent module
- **Typed** — Pydantic models enforce output schemas
- **AGENT.md** is used as the system-level guidance for all LLM prompts

---

## Scoring Weights

| Category              | Weight |
|-----------------------|--------|
| Structure             | 25%    |
| Consistency           | 20%    |
| Timeline              | 20%    |
| Risk                  | 20%    |
| Resource              | 10%    |
| Governance            | 5%     |

Scores are further adjusted by a severity-weighted penalty from findings.
