"""Deterministic synthetic data for local tests and demonstrations."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fbpipe.collect.base import Collector
from fbpipe.schema import RawPost


class SyntheticCollector(Collector):
    """Generate synthetic Vietnamese and mixed Vietnamese-English posts."""

    name = "synthetic"
    TOPICS = ("học tập", "việc làm", "lập trình", "sự kiện", "chia sẻ")
    TEMPLATES = (
        "Mọi người cho mình hỏi về {topic} với ạ.",
        "Mình muốn chia sẻ một chút về {topic}.",
        "Có thông báo mới liên quan đến {topic}.",
        "Anh chị nào biết thông tin về {topic} không?",
        "Update về {topic} nhé mọi người.",
        "Need help with {topic}, cảm ơn mọi người!",
        "Đẹpppp quá, chia sẻ về {topic}!!!",
        "Inbox mình nếu cần thêm thông tin {topic}.",
    )

    def __init__(
        self,
        n: int = 1000,
        *,
        group_id: str = "230048322891238",
        seed: int = 42,
    ) -> None:
        if n < 1:
            raise ValueError("n must be >= 1")
        self.n = n
        self.group_id = group_id
        self.seed = seed

    def iter_posts(self) -> Iterator[RawPost]:
        """Yield exactly ``n`` repeatable synthetic records."""
        rng = random.Random(self.seed)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for index in range(self.n):
            topic = self.TOPICS[index % len(self.TOPICS)]
            text = rng.choice(self.TEMPLATES).format(topic=topic)
            if index % 17 == 0:
                text += " #python"
            if index % 23 == 0:
                text += " test@example.com"
            if index % 31 == 0:
                text += " 0901234567"
            if index % 29 == 0:
                text += " https://example.invalid/post"
            if index % 41 == 0:
                text += " 😊"
            if index > 0 and index % 53 == 0:
                text = self.TEMPLATES[0].format(topic=topic)
            created_at = base + timedelta(
                days=index % 90, hours=index % 24, minutes=index % 60
            )
            post_id = hashlib.sha1(
                f"synthetic-{self.seed}-{index}".encode()
            ).hexdigest()
            content_hash = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()
            yield RawPost(
                post_id=post_id,
                group_id=self.group_id,
                permalink_path=f"/groups/{self.group_id}/posts/{post_id}",
                author_hash=hashlib.sha256(
                    f"synthetic-author-{index % 37}".encode()
                ).hexdigest(),
                created_at=created_at,
                collected_at=base,
                text=text,
                reactions_total=rng.randint(0, 200),
                comments_count=rng.randint(0, 40),
                shares_count=rng.randint(0, 20),
                source="synthetic",
                content_hash=content_hash,
            )
