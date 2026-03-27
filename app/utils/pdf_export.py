"""
Minimal PDF export utilities without external dependencies.
"""

from __future__ import annotations


def _escape_pdf_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def text_to_pdf_bytes(text: str, title: str = "Report") -> bytes:
    lines = [line.rstrip() for line in text.splitlines()]
    if not lines:
        lines = [""]

    max_lines_per_page = 48
    pages = [lines[i:i + max_lines_per_page] for i in range(0, len(lines), max_lines_per_page)]
    if not pages:
        pages = [[""]]

    objects: list[str] = []

    def add_object(content: str) -> int:
        objects.append(content)
        return len(objects)

    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    content_ids: list[int] = []
    page_ids: list[int] = []
    for page_lines in pages:
        content_lines = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
        title_line = _escape_pdf_text(title)
        content_lines.append(f"({title_line}) Tj")
        content_lines.append("T*")
        content_lines.append("( ) Tj")
        for line in page_lines:
            escaped_line = _escape_pdf_text(line[:110])
            content_lines.append(f"({escaped_line}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        stream = "\n".join(content_lines)
        content_id = add_object(
            f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}\nendstream"
        )
        content_ids.append(content_id)
        page_id = add_object(
            f"<< /Type /Page /Parent PAGES_REF /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    objects = [obj.replace("PAGES_REF", f"{pages_id} 0 R") for obj in objects]

    pdf_parts = ["%PDF-1.4\n"]
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part.encode("latin-1", errors="replace")) for part in pdf_parts))
        pdf_parts.append(f"{idx} 0 obj\n{obj}\nendobj\n")

    xref_start = sum(len(part.encode("latin-1", errors="replace")) for part in pdf_parts)
    pdf_parts.append(f"xref\n0 {len(objects) + 1}\n")
    pdf_parts.append("0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_parts.append(f"{offset:010d} 00000 n \n")
    pdf_parts.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_start}\n%%EOF"
    )
    return "".join(pdf_parts).encode("latin-1", errors="replace")
