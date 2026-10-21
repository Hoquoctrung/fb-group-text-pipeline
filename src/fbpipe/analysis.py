"""Fast, data-driven summary metrics for the first visualization slice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fbpipe.metrics import write_metrics
from fbpipe.represent.pipeline import build_classical_representations
from fbpipe.source import SOURCE_CATEGORIES, normalize_source


def load_silver(input_path: str | Path) -> pd.DataFrame:
    """Read Silver Parquet and normalize its provenance column for old files."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing Silver Parquet: {path}; run `fbpipe preprocess` first."
        )
    frame = pd.read_parquet(path)
    source_column_present = "source" in frame.columns
    frame = frame.copy()
    frame.attrs["source_column_present"] = source_column_present
    if "source" not in frame.columns:
        frame["source"] = "unknown"
    frame["source"] = frame["source"].map(normalize_source)
    return frame


def source_counts(frame: pd.DataFrame) -> dict[str, int]:
    """Count the normalized provenance categories represented in Silver."""
    values = frame.get("source", pd.Series("unknown", index=frame.index))
    normalized = values.map(normalize_source)
    counts = normalized.value_counts()
    return {category: int(counts.get(category, 0)) for category in SOURCE_CATEGORIES}


def source_caption(frame: pd.DataFrame) -> str:
    """Build a compact truthful source caption for every figure."""
    counts = source_counts(frame)
    return "Nguồn (Silver.source): " + "; ".join(
        f"{category}={counts[category]}" for category in SOURCE_CATEGORIES
    )


def _tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        return value.split()
    if isinstance(value, list | tuple):
        return [str(token) for token in value if str(token).strip()]
    return []


def _lengths(frame: pd.DataFrame) -> list[int]:
    if "n_tokens" in frame.columns:
        values = pd.to_numeric(frame["n_tokens"], errors="coerce")
        lengths: list[int] = []
        token_column = frame.get(
            "tokens_nostop",
            pd.Series([[] for _ in range(len(frame))], index=frame.index),
        )
        for position, value in enumerate(values.tolist()):
            if pd.notna(value):
                lengths.append(max(0, int(value)))
            else:
                lengths.append(len(_tokens(token_column.iloc[position])))
        return lengths
    if "tokens_nostop" in frame.columns:
        return [len(_tokens(value)) for value in frame["tokens_nostop"]]
    return [len(str(value or "").split()) for value in frame.get("text_clean", [])]


def analyze_corpus(
    *,
    input_path: str | Path = "data/silver/documents.parquet",
    data_dir: str | Path = "data",
) -> dict[str, Any]:
    """Write lightweight summary metrics without loading any transformer model."""
    frame = load_silver(input_path)
    if "doc_id" not in frame.columns:
        raise ValueError("Silver Parquet must contain a `doc_id` column.")

    dates = pd.to_datetime(
        frame.get("created_at", pd.Series(index=frame.index, dtype="object")),
        errors="coerce",
        utc=True,
    )
    daily_counts = dates.dropna().dt.strftime("%Y-%m-%d").value_counts().sort_index()
    lengths = _lengths(frame)
    sorted_lengths = sorted(lengths)
    count = len(sorted_lengths)
    length_summary = {
        "min": sorted_lengths[0] if count else 0,
        "median": sorted_lengths[count // 2] if count else 0,
        "mean": round(sum(sorted_lengths) / count, 4) if count else 0.0,
        "max": sorted_lengths[-1] if count else 0,
    }

    if frame.empty:
        top_tf: list[dict[str, Any]] = []
        top_tfidf: list[dict[str, Any]] = []
        bow_dimensions = 0
        tfidf_dimensions = 0
    else:
        classical = build_classical_representations(frame, {})
        top_tf = classical["top_tf"]
        top_tfidf = classical["top_tfidf"]
        bow_dimensions = int(classical["bow"].shape[1])
        tfidf_dimensions = int(classical["tfidf"].shape[1])

    metrics: dict[str, Any] = {
        "input_path": str(input_path),
        "n_documents": len(frame),
        "source_column_present": bool(frame.attrs.get("source_column_present", True)),
        "source_counts": source_counts(frame),
        "daily_posts": [
            {"date": str(day), "count": int(value)}
            for day, value in daily_counts.items()
        ],
        "length_distribution_tokens": length_summary,
        "lengths_tokens": lengths,
        "top_tf_terms": top_tf,
        "top_tfidf_terms": top_tfidf,
        "bow_dimensions": bow_dimensions,
        "tfidf_dimensions": tfidf_dimensions,
    }
    metrics_path = write_metrics("analyze", metrics, data_dir)
    return {**metrics, "metrics_path": str(metrics_path)}
