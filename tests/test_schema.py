from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from fbpipe.schema import RawPost


def test_raw_post_accepts_minimal_valid_record() -> None:
    post = RawPost(
        post_id="p1",
        group_id="g1",
        author_hash="a1",
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        text="hello",
        source="synthetic",
        content_hash="abc",
    )
    assert post.post_id == "p1"
    assert post.text == "hello"
    assert post.reactions_by_type == {}


def test_raw_post_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RawPost.model_validate(
            {
                "post_id": "p1",
                "group_id": "g1",
                "author_hash": "a1",
                "collected_at": datetime.now(UTC),
                "text": "hello",
                "source": "synthetic",
                "content_hash": "abc",
                "facebook_internal_field": "some_value",
            }
        )


def test_raw_post_json_round_trip(sample_post: RawPost) -> None:
    restored = RawPost.model_validate_json(sample_post.model_dump_json())
    assert restored == sample_post


def test_raw_post_defaults_missing_source_to_unknown() -> None:
    post = RawPost(
        post_id="legacy-p1",
        group_id="g1",
        author_hash="a1",
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        text="legacy record",
        content_hash="abc",
    )
    assert post.source == "unknown"


def test_raw_post_blank_source_becomes_unknown() -> None:
    post = RawPost.model_validate(
        {
            "post_id": "legacy-p2",
            "group_id": "g1",
            "author_hash": "a1",
            "collected_at": datetime(2026, 1, 1, tzinfo=UTC),
            "text": "legacy record",
            "source": " ",
            "content_hash": "abc",
        }
    )
    assert post.source == "unknown"
