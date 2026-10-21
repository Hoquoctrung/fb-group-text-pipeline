"""Small, reproducible 1k-record benchmark for SQLite FTS5 versus Parquet scans."""

from __future__ import annotations

import platform
import statistics
import tempfile
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from fbpipe.storage.parquet_store import ParquetStore
from fbpipe.storage.sqlite_store import SQLiteStore


def make_benchmark_corpus(
    frame: pd.DataFrame, n: int = 1000, seed: int = 42
) -> pd.DataFrame:
    """Bootstrap rows to n unique benchmark IDs and visibly mark all clones."""
    if frame.empty:
        raise ValueError("Cannot benchmark storage with an empty Silver dataset.")
    if n < 1:
        raise ValueError("Benchmark size n must be >= 1.")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(frame), size=n)
    source_records = cast(
        list[dict[str, Any]],
        frame.reset_index(drop=True).to_dict(orient="records"),
    )
    records: list[dict[str, Any]] = []
    for index, source_index in enumerate(indices):
        record = dict(source_records[int(source_index)])
        source_id = str(record.get("doc_id") or f"row-{source_index}")
        record["source_doc_id"] = source_id
        record["doc_id"] = f"bench-{index:06d}"
        record["is_benchmark_clone"] = True
        text = str(record.get("text_clean") or record.get("text_raw") or "")
        if text and index % 5 == 0:
            text = f"{text} benchmarkcopy{index % 17}"
        record["text_clean"] = text
        if record.get("created_at"):
            try:
                timestamp = pd.to_datetime(
                    record["created_at"], utc=True
                ).to_pydatetime()
                record["created_at"] = timestamp + timedelta(minutes=index)
                record["year_month"] = (timestamp + timedelta(minutes=index)).strftime(
                    "%Y-%m"
                )
            except (TypeError, ValueError):
                pass
        records.append(record)
    return pd.DataFrame(records)


def _timed(function: Callable[[], Any], iterations: int = 20) -> dict[str, Any]:
    """Time repeated calls and report first pass plus warm median and p95."""
    values: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        function()
        values.append(time.perf_counter() - started)
    warm = values[1:] if len(values) > 1 else values
    return {
        "iterations": iterations,
        "first_pass_seconds": round(values[0], 8),
        "warm_median_seconds": round(statistics.median(warm), 8),
        "warm_p95_seconds": round(float(np.percentile(warm, 95)), 8),
    }


def _first_search_query(frame: pd.DataFrame) -> str:
    for column in ("text_clean", "text_raw"):
        if column in frame.columns:
            for value in frame[column].fillna("").astype(str):
                terms = [term.strip(".,:;!?()[]{}\"'") for term in value.split()]
                candidate = next(
                    (term for term in terms if len(term) >= 3 and term.isalnum()),
                    "",
                )
                if candidate:
                    return candidate
    return "benchmark"


def benchmark_storage(
    frame: pd.DataFrame,
    *,
    n: int = 1000,
    seed: int = 42,
    iterations: int = 20,
) -> dict[str, Any]:
    """Benchmark 1k bootstrap-cloned docs without touching the user's main store."""
    corpus = make_benchmark_corpus(frame, n=n, seed=seed)
    query = _first_search_query(corpus)
    with tempfile.TemporaryDirectory(prefix="fbpipe-bench-") as temporary_dir:
        root = Path(temporary_dir)
        sqlite_write: list[float] = []
        parquet_write: list[float] = []
        final_sqlite_path = root / "sqlite-final.db"
        final_parquet_path = root / "parquet-final.parquet"
        for index in range(iterations):
            db_path = root / f"sqlite-write-{index:02d}.db"
            repository = SQLiteStore(db_path)
            started = time.perf_counter()
            repository.init(reset=True)
            corpus_records = cast(
                list[dict[str, Any]],
                corpus.to_dict(orient="records"),
            )
            repository.upsert_documents(corpus_records)
            sqlite_write.append(time.perf_counter() - started)
            if index == iterations - 1:
                final_sqlite_path = db_path
            parquet_path = root / f"parquet-write-{index:02d}.parquet"
            parquet_store = ParquetStore(parquet_path)
            started = time.perf_counter()
            parquet_store.write(corpus, force=True)
            parquet_write.append(time.perf_counter() - started)
            if index == iterations - 1:
                final_parquet_path = parquet_path

        sqlite_repo = SQLiteStore(final_sqlite_path)
        parquet_repo = ParquetStore(final_parquet_path)
        timestamps = pd.to_datetime(
            corpus.get("created_at", pd.Series(dtype=str)),
            errors="coerce",
            utc=True,
        ).dropna()
        if not timestamps.empty:
            start_time = (timestamps.min() - pd.Timedelta(seconds=1)).isoformat()
            end_time = (timestamps.max() + pd.Timedelta(seconds=1)).isoformat()
        else:
            start_time = "1970-01-01T00:00:00+00:00"
            end_time = "2100-01-01T00:00:00+00:00"

        sqlite_queries = {
            "Q1_keyword_search": _timed(
                lambda: sqlite_repo.keyword_search(query, limit=10), iterations
            ),
            "Q2_date_range": _timed(
                lambda: sqlite_repo.by_date_range(start_time, end_time, limit=n),
                iterations,
            ),
            "Q3_count_by_month": _timed(sqlite_repo.count_by_month, iterations),
            "Q5_count": _timed(sqlite_repo.count, iterations),
        }
        parquet_queries = {
            "Q1_keyword_scan": _timed(
                lambda: parquet_repo.keyword_search(query, limit=10), iterations
            ),
            "Q2_date_range_scan": _timed(
                lambda: parquet_repo.by_date_range(start_time, end_time, limit=n),
                iterations,
            ),
            "Q3_count_by_month_scan": _timed(parquet_repo.count_by_month, iterations),
            "Q5_count": _timed(parquet_repo.count, iterations),
        }
        sqlite_size = sum(
            path.stat().st_size for path in root.glob("sqlite-write-*.db")
        )
        parquet_size = sum(
            path.stat().st_size for path in root.glob("parquet-write-*.parquet")
        )
        return {
            "n_documents": len(corpus),
            "source_documents": len(frame),
            "cloned_from_silver": True,
            "clone_method": (
                "seeded bootstrap with unique IDs, shifted timestamps, "
                "and small text noise"
            ),
            "seed": seed,
            "iterations_per_measurement": iterations,
            "query_term": query,
            "machine": {
                "python": platform.python_version(),
                "platform": platform.platform(),
            },
            "sqlite": {
                "capabilities": [
                    "SQL",
                    "indexes",
                    "FTS5",
                    "date range",
                    "group by month",
                ],
                "bulk_write": {
                    "iterations": iterations,
                    "median_seconds": round(statistics.median(sqlite_write), 8),
                    "p95_seconds": round(float(np.percentile(sqlite_write, 95)), 8),
                    "documents_per_second_median": (
                        round(n / statistics.median(sqlite_write), 3)
                        if statistics.median(sqlite_write)
                        else None
                    ),
                },
                "queries": sqlite_queries,
                "size_bytes_all_write_runs": sqlite_size,
                "final_store_count": sqlite_repo.count(),
            },
            "parquet": {
                "capabilities": [
                    "columnar file",
                    "substring scan",
                    "date range scan",
                    "group by month",
                ],
                "bulk_write": {
                    "iterations": iterations,
                    "median_seconds": round(statistics.median(parquet_write), 8),
                    "p95_seconds": round(float(np.percentile(parquet_write, 95)), 8),
                    "documents_per_second_median": (
                        round(n / statistics.median(parquet_write), 3)
                        if statistics.median(parquet_write)
                        else None
                    ),
                },
                "queries": parquet_queries,
                "size_bytes_all_write_runs": parquet_size,
                "final_store_count": parquet_repo.count(),
            },
            "notes": [
                (
                    "Benchmark uses cloned Silver records with new IDs; it is not a "
                    "count of real Facebook posts."
                ),
                (
                    "First-pass latency is an observation, not a guaranteed "
                    "OS-cache-cold measurement."
                ),
                "Parquet uses scans; SQLite uses the FTS5 text index.",
                (
                    "Q4 vector search is omitted because neither minimal store "
                    "has vector indexing."
                ),
            ],
        }
