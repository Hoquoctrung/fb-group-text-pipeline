"""Import collector for permitted JSONL or CSV data."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import unicodedata
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fbpipe.collect.base import Collector
from fbpipe.privacy import hash_author, scrub_pii
from fbpipe.schema import RawPost

logger = logging.getLogger(__name__)


class ImportCollector(Collector):
    """Read and validate posts from JSONL or CSV files."""

    name = "import"

    def __init__(
        self, path: str | Path, *, group_id: str, salt: str | None = None
    ) -> None:
        self.path = Path(path)
        self.group_id = group_id
        self.salt = os.getenv("FBPIPE_SALT", "") if salt is None else salt
        self.errors: list[str] = []

    def iter_posts(self) -> Iterator[RawPost]:
        """Yield valid records and collect readable row-level errors."""
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        suffix = self.path.suffix.lower()
        if suffix == ".jsonl":
            yield from self._iter_jsonl()
        elif suffix == ".csv":
            yield from self._iter_csv()
        else:
            raise ValueError("Only .jsonl and .csv files are supported")

    def _iter_jsonl(self) -> Iterator[RawPost]:
        with self.path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("each JSONL line must be an object")
                    yield self._row_to_post(row)
                except (ValueError, TypeError, KeyError) as exc:
                    message = f"line {line_number}: {exc}"
                    self.errors.append(message)
                    logger.warning("Skipping invalid import row: %s", message)

    def _iter_csv(self) -> Iterator[RawPost]:
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                try:
                    yield self._row_to_post(row)
                except (ValueError, TypeError, KeyError) as exc:
                    message = f"line {row_number}: {exc}"
                    self.errors.append(message)
                    logger.warning("Skipping invalid import row: %s", message)

    def _row_to_post(self, row: dict[str, Any]) -> RawPost:
        raw_text = str(row.get("text", "")).strip()
        if not raw_text:
            raise ValueError("text is required")
        if not self.salt:
            raise ValueError("FBPIPE_SALT is required to hash imported author IDs")
        author = str(row.get("author") or "unknown")
        author_hash = hash_author(author, self.salt)
        created_at = self._parse_datetime(row.get("created_at"))
        collected_at = datetime.now(UTC)
        clean_text = unicodedata.normalize("NFC", scrub_pii(raw_text))
        post_id = str(row.get("post_id") or "").strip()
        if not post_id:
            fingerprint = f"{author_hash}|{created_at}|{clean_text[:200]}"
            post_id = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()
        content_hash = hashlib.sha1(clean_text.encode("utf-8")).hexdigest()
        return RawPost(
            post_id=post_id,
            group_id=self.group_id,
            permalink_path=None,
            author_hash=author_hash,
            created_at=created_at,
            collected_at=collected_at,
            text=clean_text,
            reactions_total=self._int_or_none(row.get("reactions")),
            comments_count=self._int_or_none(row.get("comments_count")),
            shares_count=self._int_or_none(row.get("shares_count")),
            source="import",
            content_hash=content_hash,
        )

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value in (None, ""):
            return None
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 0:
            raise ValueError("count fields must be non-negative")
        return parsed
