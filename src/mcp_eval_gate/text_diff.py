"""Readable descriptions of how two strings differ, for failure details in reports."""

from __future__ import annotations

import os

DEFAULT_CONTEXT = 20
DEFAULT_PREVIEW_LIMIT = 120


def describe_difference(expected: str, actual: str, context: int = DEFAULT_CONTEXT) -> str:
    index = _first_difference(expected, actual)
    return (
        f"first difference at char {index} "
        f"(expected {len(expected)} chars, got {len(actual)}): "
        f"expected {_snippet(expected, index, context)!r}, got {_snippet(actual, index, context)!r}"
    )


def preview(text: str, limit: int = DEFAULT_PREVIEW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… (+{len(text) - limit} more chars)"


def _first_difference(expected: str, actual: str) -> int:
    return len(os.path.commonprefix([expected, actual]))


def _snippet(text: str, index: int, context: int) -> str:
    start = max(0, index - context)
    end = min(len(text), index + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"
