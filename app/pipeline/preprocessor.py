"""
Preprocessing Layer — cleans and normalises raw text before section extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.input_layer import RawInput


@dataclass
class PreprocessedText:
    cleaned_text: str
    line_count: int
    word_count: int
    char_count: int


_MULTI_BLANK = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def preprocess(raw: RawInput) -> PreprocessedText:
    text = raw.raw_text

    # Strip control characters (but keep \n, \t)
    text = _CONTROL_CHARS.sub("", text)

    # Normalise Windows line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace per line
    text = _TRAILING_SPACES.sub("", text)

    # Collapse excessive blank lines to a single blank line
    text = _MULTI_BLANK.sub("\n\n", text)

    text = text.strip()

    lines = text.splitlines()
    words = text.split()

    return PreprocessedText(
        cleaned_text=text,
        line_count=len(lines),
        word_count=len(words),
        char_count=len(text),
    )
