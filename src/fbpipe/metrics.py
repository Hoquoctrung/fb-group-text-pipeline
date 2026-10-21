"""Persistence for stage metrics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_metrics(
    stage: str,
    metrics: dict[str, Any],
    data_dir: str | Path = "data",
) -> Path:
    """Write a JSON metrics file for a completed stage."""
    metrics_dir = Path(data_dir) / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "created_at": datetime.now(UTC).isoformat(),
        **metrics,
    }
    output = metrics_dir / f"{stage}.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output
