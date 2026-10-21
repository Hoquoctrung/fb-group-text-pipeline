"""Contract-like tests for SQLite FTS5 and Parquet persistence."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from fbpipe.storage.benchmark import make_benchmark_corpus
from fbpipe.storage.parquet_store import ParquetStore
from fbpipe.storage.sqlite_store import SQLiteStore


def _docs() -> list[dict[str, object]]:
    return [
        {
            "doc_id": "doc-1",
            "created_at": datetime(2026, 1, 2, tzinfo=UTC),
            "year_month": "2026-01",
            "lang": "vi",
            "text_clean": "piano music lesson",
            "tokens_nostop": ["piano", "music"],
            "keep": True,
        },
        {
            "doc_id": "doc-2",
            "created_at": datetime(2026, 2, 2, tzinfo=UTC),
            "year_month": "2026-02",
            "lang": "en",
            "text_clean": "developer job listing",
            "tokens_nostop": ["developer", "job"],
            "keep": True,
        },
    ]


def test_sqlite_upsert_is_idempotent_and_fts_searches(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "documents.db")
    store.init()
    assert store.upsert_documents(_docs()) == 2
    assert store.upsert_documents(_docs()) == 2
    assert store.count() == 2
    hits = store.keyword_search("piano", limit=10)
    assert len(hits) == 1
    assert hits[0]["doc_id"] == "doc-1"
    assert len(store.by_date_range("2026-01-01", "2026-02-01", limit=10)) == 1
    assert store.count_by_month() == [("2026-01", 1), ("2026-02", 1)]
    assert store.file_size_bytes() > 0


def test_sqlite_fts_multiword_query(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "documents.db")
    store.upsert_documents(_docs())
    hits = store.keyword_search("piano music", limit=10)
    assert [hit["doc_id"] for hit in hits] == ["doc-1"]


def test_parquet_store_round_trip(tmp_path) -> None:
    pytest.importorskip("pyarrow")
    path = tmp_path / "documents.parquet"
    store = ParquetStore(path)
    assert store.write(pd.DataFrame(_docs())) == 2
    assert store.count() == 2
    assert len(store.keyword_search("piano")) == 1
    assert len(store.by_date_range("2026-01-01", "2026-02-01")) == 1
    with pytest.raises(FileExistsError):
        store.write(pd.DataFrame(_docs()))
    assert store.write(pd.DataFrame(_docs()), force=True) == 2


def test_benchmark_corpus_has_unique_ids_and_clone_marker() -> None:
    frame = pd.DataFrame(_docs())
    benchmark = make_benchmark_corpus(frame, n=25, seed=42)
    assert len(benchmark) == 25
    assert benchmark["doc_id"].is_unique
    assert benchmark["is_benchmark_clone"].all()
    assert set(benchmark["source_doc_id"]).issubset({"doc-1", "doc-2"})


def test_sqlite_accepts_array_values_from_parquet(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    store = SQLiteStore(tmp_path / "documents.db")
    document = _docs()[0] | {
        "tokens_nostop": np.array(["piano", "music"]),
        "hashtags": np.array(["lesson", "piano"]),
    }

    assert store.upsert_documents([document]) == 1
    hits = store.keyword_search("piano", limit=10)
    assert len(hits) == 1
    assert hits[0]["tokens_nostop"] == ["piano", "music"]
    assert hits[0]["hashtags"] == ["lesson", "piano"]
