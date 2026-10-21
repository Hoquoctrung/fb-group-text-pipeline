"""Normalize provenance labels shared by collection and analysis stages."""

from __future__ import annotations

from typing import Any

SOURCE_CATEGORIES = ("synthetic", "import", "playwright", "unknown")


def normalize_source(value: Any) -> str:
    """Map raw collector values to the small public Silver source vocabulary."""
    if value is None:
        return "unknown"
    normalized = str(value).strip().casefold()
    if not normalized or normalized in {"nan", "none", "null", "<na>"}:
        return "unknown"
    if normalized in {"synthetic", "import"}:
        return normalized
    if normalized.startswith("playwright"):
        return "playwright"
    return "unknown"
