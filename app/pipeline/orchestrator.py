"""
Pipeline Orchestrator — hybrid analysis pipeline.

Execution order:
  1. Input ingestion
  2. Preprocessing
  3. Section extraction (regex primary, LLM fallback)
  4. Rule engine (deterministic, always runs)
  5. LLM insight engine (optional, enriches rule findings)
  6. Scoring (deterministic, from rule findings only)
  7. Report assembly
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.llm.openrouter import llm_available as _llm_provider_available
from app.llm_engine.insights import generate_insights
from app.pipeline.input_layer import RawInput, ingest_file, ingest_text
from app.pipeline.preprocessor import preprocess
from app.pipeline.report_generator import AuditReport, generate_report
from app.pipeline.scoring_engine import compute_scores
from app.pipeline.section_extractor import extract_sections
from app.rule_engine.runner import run_rules


@dataclass
class PipelineResult:
    """Returned by run_pipeline_full() — adds the cleaned plan text used as input."""
    report: AuditReport
    plan_text: str

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when a pipeline stage fails with a user-facing message."""


def run_pipeline_full(
    text: Optional[str] = None,
    filename: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    project_type: str = "general",
    enable_llm: bool = True,
    progress_callback=None,
) -> PipelineResult:
    """
    Execute the full pipeline and return both the report and the cleaned plan
    text. Most callers should use `run_pipeline()` which returns just the
    report; this variant is needed by features that operate on the plan text
    after audit (e.g. the chat assistant).
    """

    def _progress(stage: str, pct: int) -> None:
        if progress_callback:
            progress_callback(stage, pct)

    llm_available = enable_llm and _llm_provider_available()

    # ── Stage 1: Input ────────────────────────────────────────────────────────
    _progress("Ingesting input", 5)
    try:
        if file_bytes and filename:
            raw: RawInput = ingest_file(filename, file_bytes)
        elif text:
            raw = ingest_text(text)
        else:
            raise PipelineError("No input provided. Upload a file or paste text.")
    except ValueError as exc:
        raise PipelineError(str(exc)) from exc

    # ── Stage 2: Preprocessing ────────────────────────────────────────────────
    _progress("Preprocessing text", 10)
    preprocessed = preprocess(raw)

    if preprocessed.word_count < 50:
        raise PipelineError(
            f"Input is too short ({preprocessed.word_count} words). "
            "Please provide a more complete project plan."
        )

    # ── Stage 3: Section Extraction ───────────────────────────────────────────
    _progress("Extracting sections", 18)
    try:
        sections = extract_sections(preprocessed, allow_llm_fallback=llm_available)
    except Exception as exc:
        raise PipelineError(f"Section extraction failed: {exc}") from exc

    # ── Stage 4: Rule Engine (deterministic) ──────────────────────────────────
    _progress("Running rule checks", 30)
    try:
        bundle = run_rules(sections, project_type=project_type)
    except Exception as exc:
        raise PipelineError(f"Rule engine failed: {exc}") from exc

    # ── Stage 5: LLM Insight Engine (optional) ────────────────────────────────
    if llm_available:
        _progress("Generating AI insights", 65)
        try:
            bundle = generate_insights(sections, bundle)
        except Exception as exc:
            # Non-fatal — log and continue with rule findings only
            logger.warning("LLM insight layer failed (non-fatal): %s", exc)
    else:
        _progress("Skipping AI insights (offline mode)", 65)

    # ── Stage 6: Scoring (deterministic) ─────────────────────────────────────
    _progress("Computing scores", 85)
    scores = compute_scores(bundle)

    # ── Stage 7: Report Assembly ──────────────────────────────────────────────
    _progress("Assembling report", 95)
    report = generate_report(
        source_name=raw.filename,
        project_type=project_type,
        word_count=preprocessed.word_count,
        sections=sections,
        bundle=bundle,
        scores=scores,
        llm_enabled=llm_available,
    )

    _progress("Complete", 100)
    return PipelineResult(report=report, plan_text=preprocessed.cleaned_text)


def run_pipeline(
    text: Optional[str] = None,
    filename: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    project_type: str = "general",
    enable_llm: bool = True,
    progress_callback=None,
) -> AuditReport:
    """
    Execute the full hybrid analysis pipeline.

    Parameters
    ----------
    text         : pasted plain text input
    filename     : name of uploaded file (with extension)
    file_bytes   : raw bytes of uploaded file
    enable_llm   : whether to run the LLM insight layer (default: True)
                   Set False to run fully offline / deterministic mode.
    progress_callback(stage: str, pct: int) : optional UI progress hook
    """
    return run_pipeline_full(
        text=text,
        filename=filename,
        file_bytes=file_bytes,
        project_type=project_type,
        enable_llm=enable_llm,
        progress_callback=progress_callback,
    ).report
