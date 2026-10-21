"""Simple Parquet persistence and scans for the Silver document table."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd


class ParquetStore:
    """Write document records to Parquet and scan them with pandas/pyarrow."""

    name = "parquet"
    capabilities = {"columnar", "aggregate"}

    def __init__(self, path: str | Path = "data/store/documents.parquet") -> None:
        self.path = Path(path)

    def write(
        self,
        docs: pd.DataFrame | Sequence[Mapping[str, Any]],
        *,
        force: bool = False,
    ) -> int:
        """Write records to a single Parquet file atomically."""
        if self.path.exists() and not force:
            raise FileExistsError(
                f"Parquet output exists: {self.path}; pass --force to replace it."
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        frame = (
            docs.copy() if isinstance(docs, pd.DataFrame) else pd.DataFrame(list(docs))
        )
        temp_path = self.path.with_name(f".{self.path.stem}.tmp.parquet")
        try:
            frame.to_parquet(temp_path, index=False)
            temp_path.replace(self.path)
        except ImportError as exc:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Parquet support is missing; install the project dependencies "
                "including pyarrow."
            ) from exc
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return len(frame)

    def read(self) -> pd.DataFrame:
        """Load the Parquet file into a DataFrame."""
        if not self.path.exists():
            raise FileNotFoundError(f"Missing Parquet file: {self.path}")
        return pd.read_parquet(self.path)

    def count(self) -> int:
        """Count stored rows."""
        return len(self.read())

    def keyword_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Do a substring scan; Parquet does not provide a full-text index."""
        if limit < 1 or not query.strip():
            return []
        frame = self.read()
        column = "text_clean" if "text_clean" in frame.columns else "text_raw"
        mask = (
            frame[column]
            .fillna("")
            .astype(str)
            .str.contains(re.escape(query), case=False, regex=True)
        )
        return frame.loc[mask].head(limit).to_dict(orient="records")

    def by_date_range(
        self, start: str, end: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Scan records within the half-open timestamp interval [start, end)."""
        frame = self.read()
        if "created_at" not in frame.columns:
            return []
        created = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
        start_time = pd.to_datetime(start, utc=True)
        end_time = pd.to_datetime(end, utc=True)
        mask = (created >= start_time) & (created < end_time)
        return frame.loc[mask].head(limit).to_dict(orient="records")

    def count_by_month(self) -> list[tuple[str, int]]:
        """Aggregate counts by the Silver year_month field."""
        frame = self.read()
        if "year_month" not in frame.columns:
            return []
        grouped = (
            frame.dropna(subset=["year_month"])
            .groupby("year_month")
            .size()
            .sort_index()
        )
        return [(str(key), int(value)) for key, value in grouped.items()]

    def file_size_bytes(self) -> int:
        """Return the Parquet file size on disk."""
        return self.path.stat().st_size if self.path.exists() else 0
