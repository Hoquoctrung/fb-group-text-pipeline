"""SQLite document repository with FTS5 keyword search."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return str(value.isoformat())
        except (TypeError, ValueError):
            return str(value)
    text = str(value).strip()
    return text or None


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    # NumPy arrays expose both ``item`` and ``tolist``. Convert arrays first:
    # ``item()`` fails for arrays with more than one element.
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


class SQLiteStore:
    """Persist Silver document records and provide indexed query operations."""

    name = "sqlite"
    capabilities = {"sql", "fts", "aggregate"}

    def __init__(self, path: str | Path = "data/fbpipe.db") -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self, *, reset: bool = False) -> None:
        """Create tables/indexes and require the SQLite build's FTS5 capability."""
        with self._connect() as connection:
            if reset:
                connection.execute("DROP TABLE IF EXISTS posts_fts")
                connection.execute("DROP TABLE IF EXISTS posts")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    doc_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    year_month TEXT,
                    lang TEXT,
                    author_hash TEXT,
                    text_clean TEXT NOT NULL DEFAULT '',
                    tokens_nostop TEXT NOT NULL DEFAULT '[]',
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_lang ON posts(lang)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_year_month ON posts(year_month)"
            )
            try:
                connection.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts "
                    "USING fts5(doc_id UNINDEXED, text_clean)"
                )
            except sqlite3.OperationalError as exc:
                raise RuntimeError(
                    "This SQLite build does not support FTS5; use a Python "
                    "distribution with FTS5 enabled."
                ) from exc

    def upsert_documents(self, docs: Iterable[Mapping[str, Any]]) -> int:
        """Insert or update documents and keep their FTS entries in sync."""
        self.init()
        count = 0
        with self._connect() as connection:
            for raw_doc in docs:
                doc = dict(raw_doc)
                doc_id = str(doc.get("doc_id") or "").strip()
                if not doc_id:
                    continue
                created_at = _iso(doc.get("created_at"))
                text_clean = str(doc.get("text_clean") or doc.get("text_raw") or "")
                tokens = doc.get("tokens_nostop")
                if tokens is None or type(tokens).__name__ == "NAType":
                    tokens = []
                elif hasattr(tokens, "tolist"):
                    # Parquet list columns may be returned as NumPy arrays.
                    # Avoid boolean-testing an array (its truth value is ambiguous).
                    tokens = tokens.tolist()
                if isinstance(tokens, float) and tokens != tokens:
                    # Normalize a scalar NaN to an empty token list.
                    tokens = []
                connection.execute(
                    """
                    INSERT INTO posts(doc_id, created_at, year_month, lang, author_hash,
                                      text_clean, tokens_nostop, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_id) DO UPDATE SET
                        created_at=excluded.created_at,
                        year_month=excluded.year_month,
                        lang=excluded.lang,
                        author_hash=excluded.author_hash,
                        text_clean=excluded.text_clean,
                        tokens_nostop=excluded.tokens_nostop,
                        payload_json=excluded.payload_json
                    """,
                    (
                        doc_id,
                        created_at,
                        _iso(doc.get("year_month")),
                        _iso(doc.get("lang")),
                        _iso(doc.get("author_hash")),
                        text_clean,
                        json.dumps(tokens, ensure_ascii=False, default=_json_default),
                        json.dumps(doc, ensure_ascii=False, default=_json_default),
                    ),
                )
                connection.execute("DELETE FROM posts_fts WHERE doc_id = ?", (doc_id,))
                connection.execute(
                    "INSERT INTO posts_fts(doc_id, text_clean) VALUES (?, ?)",
                    (doc_id, text_clean),
                )
                count += 1
        return count

    def count(self) -> int:
        """Return the number of unique document IDs."""
        self.init()
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM posts").fetchone()
            return int(row["n"])

    def keyword_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search terms using SQLite FTS5; return matching stored payloads."""
        self.init()
        terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
        if not terms or limit < 1:
            return []
        fts_query = " AND ".join(
            f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms
        )
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT posts.payload_json
                FROM posts_fts JOIN posts USING (doc_id)
                WHERE posts_fts MATCH ?
                ORDER BY bm25(posts_fts)
                LIMIT ?
                """,
                (fts_query, int(limit)),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def by_date_range(
        self, start: datetime | str, end: datetime | str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return records in the half-open timestamp interval [start, end)."""
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM posts
                WHERE created_at >= ? AND created_at < ?
                ORDER BY created_at LIMIT ?
                """,
                (_iso(start), _iso(end), int(limit)),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def count_by_month(self) -> list[tuple[str, int]]:
        """Aggregate document counts by year-month."""
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT year_month, COUNT(*) AS n FROM posts "
                "WHERE year_month IS NOT NULL GROUP BY year_month ORDER BY year_month"
            ).fetchall()
        return [(str(row["year_month"]), int(row["n"])) for row in rows]

    def file_size_bytes(self) -> int:
        """Return database file size on disk, excluding transient journal files."""
        return self.path.stat().st_size if self.path.exists() else 0
