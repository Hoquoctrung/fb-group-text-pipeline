"""Atomic checkpoint persistence for resumable collection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Checkpoint:
    """State needed to resume a crawl without yielding seen post IDs."""

    seen_ids: set[str] = field(default_factory=set)
    scroll_count: int = 0
    last_created_at: str | None = None
    run_id: str | None = None

    def save(self, path: str | Path) -> None:
        """Atomically persist checkpoint JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload["seen_ids"] = sorted(self.seen_ids)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(target)

    @classmethod
    def load(cls, path: str | Path) -> Checkpoint:
        """Load a checkpoint, or return a fresh empty checkpoint if absent."""
        target = Path(path)
        if not target.exists():
            return cls(seen_ids=set())
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["seen_ids"] = set(payload.get("seen_ids", []))
        return cls(**payload)

    def has_seen(self, post_id: str) -> bool:
        """Return whether this ID was already persisted/seen."""
        return post_id in self.seen_ids

    def mark_seen(self, post_id: str) -> None:
        """Mark a post ID in the in-memory checkpoint."""
        self.seen_ids.add(post_id)
