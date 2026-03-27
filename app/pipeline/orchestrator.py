"""
Pipeline Orchestrator — runs all stages in sequence and returns a final AuditReport.
This is the single entry point for the UI layer.
"""

from __future__ import annotations

from typing import Optional

from app.analysis.consistency_analysis import run_consistency_analysis
from app.analysis.governance_analysis import run_governance_analysis
from app.analysis.models import AnalysisBundle
from app.analysis.resource_analysis import run_resource_analysis
from app.analysis.risk_analysis import run_risk_analysis
from app.analysis.structure_analysis import run_structure_analysis
from app.analysis.timeline_analysis import run_timeline_analysis
from app.pipeline.input_layer import RawInput, ingest_file, ingest_text
from app.pipeline.preprocessor import preprocess
from app.pipeline.report_generator import AuditReport, generate_report
from app.pipeline.scoring_engine import compute_scores
from app.pipeline.section_extractor import extract_sections


class PipelineError(Exception):
    """Raised when a pipeline stage fails with a user-facing message."""


def run_pipeline(
    text: Optional[str] = None,
    filename: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    progress_callback=None,
) -> AuditReport:
    """
    Execute the full analysis pipeline.

    Provide either:
    - text: plain text string (pasted input)
    - filename + file_bytes: uploaded file

    progress_callback(stage: str, pct: int) is called at each stage if provided.
    """

    def _progress(stage: str, pct: int) -> None:
        if progress_callback:
            progress_callback(stage, pct)

    # --- Stage 1: Input ---
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

    # --- Stage 2: Preprocessing ---
    _progress("Preprocessing text", 10)
    preprocessed = preprocess(raw)

    if preprocessed.word_count < 50:
        raise PipelineError(
            f"Input is too short ({preprocessed.word_count} words). "
            "Please provide a more complete project plan."
        )

    # --- Stage 3: Section Extraction ---
    _progress("Extracting sections", 20)
    try:
        sections = extract_sections(preprocessed)
    except Exception as exc:
        raise PipelineError(f"Section extraction failed: {exc}") from exc

    # --- Stage 4: Analysis Engine ---
    _progress("Analysing structure", 30)
    try:
        structure = run_structure_analysis(sections)
    except Exception as exc:
        raise PipelineError(f"Structure analysis failed: {exc}") from exc

    _progress("Analysing consistency", 45)
    try:
        consistency = run_consistency_analysis(sections)
    except Exception as exc:
        raise PipelineError(f"Consistency analysis failed: {exc}") from exc

    _progress("Analysing timeline", 57)
    try:
        timeline = run_timeline_analysis(sections)
    except Exception as exc:
        raise PipelineError(f"Timeline analysis failed: {exc}") from exc

    _progress("Analysing risks", 68)
    try:
        risk = run_risk_analysis(sections)
    except Exception as exc:
        raise PipelineError(f"Risk analysis failed: {exc}") from exc

    _progress("Analysing resources", 78)
    try:
        resource = run_resource_analysis(sections)
    except Exception as exc:
        raise PipelineError(f"Resource analysis failed: {exc}") from exc

    _progress("Analysing governance", 87)
    try:
        governance = run_governance_analysis(sections)
    except Exception as exc:
        raise PipelineError(f"Governance analysis failed: {exc}") from exc

    bundle = AnalysisBundle(
        structure=structure,
        consistency=consistency,
        timeline=timeline,
        risk=risk,
        resource=resource,
        governance=governance,
    )

    # --- Stage 5: Scoring ---
    _progress("Computing scores", 93)
    scores = compute_scores(bundle)

    # --- Stage 6: Report Generation ---
    _progress("Generating report", 97)
    report = generate_report(
        source_name=raw.filename,
        word_count=preprocessed.word_count,
        sections=sections,
        bundle=bundle,
        scores=scores,
    )

    _progress("Complete", 100)
    return report
