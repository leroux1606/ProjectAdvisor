"""
Prompt builders for the chat assistant.

The assistant is scoped to a single loaded plan and its audit report. It can
explain findings, summarise the plan, and answer questions about it. It is
explicitly NOT a free agent — it cannot run code, call external tools, or
modify the plan. Write actions are handled separately by the verb dispatcher.
"""

from __future__ import annotations

from app.pipeline.report_generator import AuditReport


SYSTEM_PROMPT = """You are an assistant for a single project plan and its audit report.

Your role is strictly bounded:
- Answer questions about the plan and its findings.
- Explain rule findings in plain language when asked.
- Summarise sections, risks, or the plan as a whole on request.
- Suggest improvements grounded in the actual content.

Hard rules:
- Do NOT invent content that is not in the plan or report.
- Do NOT claim that scoring would change — scoring is deterministic.
- Do NOT execute, request, or describe shell commands, code execution, or
  external tool calls.
- If the user asks you to rewrite or change the plan, reply that they should
  use the Quick Actions panel and explain which action would help.
- Keep replies concise — under 250 words unless the user asks for detail.
- Do not include HTML or scripts in replies.
"""


_REPORT_TRUNCATION_CHARS = 8000


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[…truncated…]"


def build_context_message(plan_text: str, report: AuditReport) -> str:
    """
    Build the initial assistant-context message that grounds the conversation.
    Sent as a `system`-role message after the main system prompt.
    """
    findings_lines: list[str] = []
    for cat in report.category_results:
        for f in cat.rule_findings:
            findings_lines.append(
                f"- [{f.severity.value.upper()}] {f.rule_id} · {f.title} — {f.explanation}"
            )

    findings_block = "\n".join(findings_lines) if findings_lines else "(no rule findings)"

    return f"""# Loaded plan

Source: {report.source_name or "(pasted text)"}
Project type: {report.project_type}
Word count: {report.word_count}
Overall score: {report.overall_score:.1f} (grade {report.grade})
Sections found: {", ".join(report.sections_found) or "none"}
Sections missing: {", ".join(report.sections_missing) or "none"}

## Plan text

{_truncate(plan_text, _REPORT_TRUNCATION_CHARS)}

## Rule findings

{findings_block}
"""
