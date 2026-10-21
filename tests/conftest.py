from datetime import UTC, datetime

import pytest

from fbpipe.schema import RawPost


@pytest.fixture
def sample_post() -> RawPost:
    return RawPost(
        post_id="fixture-post-001",
        group_id="fixture-group",
        permalink_path="/fixture/post/001",
        author_hash="fixture-author-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        collected_at=datetime(2026, 1, 2, tzinfo=UTC),
        text="Đây là bài viết fixture.",
        reactions_total=10,
        comments_count=2,
        shares_count=1,
        source="synthetic",
        content_hash="fixture-content-hash",
    )
