import pytest

from fbpipe.privacy import hash_author, scrub_pii


def test_hash_author_is_deterministic() -> None:
    assert hash_author("author-123", "test-salt") == hash_author(
        "author-123", "test-salt"
    )
    assert hash_author("author-123", "test-salt") != "author-123"


def test_hash_author_changes_with_salt() -> None:
    assert hash_author("author-123", "salt-a") != hash_author("author-123", "salt-b")


def test_hash_author_requires_salt() -> None:
    with pytest.raises(ValueError):
        hash_author("author-123", "")


def test_scrub_pii() -> None:
    result = scrub_pii(
        "Email test@example.com, phone 0901234567, link https://example.com/a."
    )
    assert "<EMAIL>" in result
    assert "<PHONE>" in result
    assert "<URL>" in result
    assert "test@example.com" not in result
    assert "0901234567" not in result
