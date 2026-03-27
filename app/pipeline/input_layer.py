"""
Input Layer — accepts raw project plan content from file upload or text paste.
Produces a normalized RawInput object for downstream processing.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawInput:
    source: str          # "upload" | "text"
    filename: Optional[str]
    raw_text: str


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import PyPDF2  # noqa: PLC0415

        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except Exception as exc:
        raise ValueError(f"PDF extraction failed: {exc}") from exc


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document  # noqa: PLC0415

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as exc:
        raise ValueError(f"DOCX extraction failed: {exc}") from exc


def extract_text_from_txt(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode text file with any supported encoding.")


_EXTRACTORS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".txt": extract_text_from_txt,
    ".md": extract_text_from_txt,
}


def ingest_file(filename: str, file_bytes: bytes) -> RawInput:
    """Parse an uploaded file into a RawInput."""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    extractor = _EXTRACTORS.get(suffix)
    if extractor is None:
        raise ValueError(f"Unsupported file type: '{suffix}'. Accepted: PDF, DOCX, TXT, MD.")
    raw_text = extractor(file_bytes)
    if not raw_text.strip():
        raise ValueError("The uploaded file appears to be empty or could not be read.")
    return RawInput(source="upload", filename=filename, raw_text=raw_text)


def ingest_text(text: str) -> RawInput:
    """Accept pasted plain text as a RawInput."""
    if not text or not text.strip():
        raise ValueError("Input text is empty.")
    return RawInput(source="text", filename=None, raw_text=text)
