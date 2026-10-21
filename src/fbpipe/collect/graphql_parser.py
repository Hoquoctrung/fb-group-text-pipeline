"""Defensive generic parser for captured JSON responses.

TODO(real-sample): Update extraction rules only after inspecting anonymized
probe samples. The generic keys below are fixture keys, not a claim about
Facebook's private GraphQL schema.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from typing import Any

from fbpipe.privacy import hash_author, scrub_pii
from fbpipe.schema import RawPost


def iter_json_values(payload: str) -> Iterator[Any]:
    """Parse concatenated JSON values, failing clearly on malformed input."""
    decoder = json.JSONDecoder()
    position = 0
    while position < len(payload):
        while position < len(payload) and payload[position].isspace():
            position += 1
        if position >= len(payload):
            return
        value, end = decoder.raw_decode(payload, position)
        yield value
        position = end


def find_nodes(
    obj: Any, predicate: Callable[[Mapping[str, Any]], bool]
) -> Iterator[Mapping[str, Any]]:
    """Recursively yield mapping nodes satisfying a caller-provided predicate."""
    if isinstance(obj, Mapping):
        if predicate(obj):
            yield obj
        for value in obj.values():
            yield from find_nodes(value, predicate)
    elif isinstance(obj, list):
        for value in obj:
            yield from find_nodes(value, predicate)


def safe_get(obj: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
    """Return the first value found at one of the candidate nested paths."""
    for path in paths:
        current: Any = obj
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                break
            current = current[key]
        else:
            return current
    return None


def _looks_like_post(node: Mapping[str, Any]) -> bool:
    """Identify only generic fixture-shaped text+timestamp records."""
    text = safe_get(node, ("text",), ("message",), ("content",))
    created = safe_get(node, ("created_at",), ("createdAt",), ("timestamp",))
    return isinstance(text, str) and bool(text.strip()) and created is not None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse ISO strings or Unix timestamps to UTC."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def parse_response(
    payload: str,
    *,
    group_id: str,
    collected_at: datetime | None = None,
    salt: str | None = None,
) -> list[RawPost]:
    """Parse only the generic fixture shape; never retain raw author IDs."""
    collected_at = collected_at or datetime.now(UTC)
    salt = salt or os.getenv("FBPIPE_SALT")
    posts: list[RawPost] = []
    for root in iter_json_values(payload):
        for node in find_nodes(root, _looks_like_post):
            text_value = safe_get(node, ("text",), ("message",), ("content",))
            created_value = safe_get(
                node, ("created_at",), ("createdAt",), ("timestamp",)
            )
            post_id_value = safe_get(node, ("post_id",), ("id",))
            if not isinstance(text_value, str) or post_id_value is None:
                continue
            created_at = _parse_datetime(created_value)
            if created_at is None:
                continue
            author_value = safe_get(node, ("author_id",), ("author", "id"))
            if author_value is not None and not salt:
                # Do not persist raw identifiers when no HMAC salt is configured.
                author_hash = "unknown"
            elif author_value is not None:
                author_hash = hash_author(str(author_value), salt or "")
            else:
                author_hash = "unknown"
            clean_text = scrub_pii(text_value.strip())
            content_hash = hashlib.sha1(clean_text.encode("utf-8")).hexdigest()
            posts.append(
                RawPost(
                    post_id=str(post_id_value),
                    group_id=group_id,
                    permalink_path=None,
                    author_hash=author_hash,
                    created_at=created_at,
                    collected_at=collected_at,
                    text=clean_text,
                    source="playwright_graphql",
                    content_hash=content_hash,
                )
            )
    return posts
