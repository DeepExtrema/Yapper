"""Lightweight text formatter for post-transcription cleanup."""

from __future__ import annotations

import re


def format_text(text: str) -> str:
    """Clean up transcribed text: fix spacing, punctuation, and capitalization."""
    if not text or not text.strip():
        return ""

    result = text.strip()

    # Collapse multiple spaces to single space
    result = re.sub(r" {2,}", " ", result)

    # Remove space before punctuation: . , ! ? ; :
    result = re.sub(r" ([.,!?;:])", r"\1", result)

    # Ensure space after sentence-ending punctuation (.!?) if followed by a letter
    result = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", result)

    # Capitalize first character
    if result:
        result = result[0].upper() + result[1:]

    # Capitalize first letter after sentence-ending punctuation
    result = re.sub(r"([.!?])\s+([a-z])", lambda m: m.group(1) + " " + m.group(2).upper(), result)

    return result
