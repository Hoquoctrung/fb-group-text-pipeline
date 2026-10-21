from pathlib import Path

import pytest

from fbpipe.collect.graphql_parser import find_nodes, iter_json_values, parse_response

FIXTURE = Path(__file__).parent / "fixtures" / "graphql_sample.txt"


def test_iter_json_values_supports_concatenated_json() -> None:
    assert list(iter_json_values('{"a": 1}\n{"b": 2}')) == [{"a": 1}, {"b": 2}]


def test_iter_json_values_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError):
        list(iter_json_values('{"a": }'))


def test_find_nodes() -> None:
    payload = {
        "data": {"items": [{"id": "1", "text": "one"}, {"id": "2", "other": "two"}]}
    }
    nodes = list(find_nodes(payload, lambda node: "text" in node))
    assert nodes == [{"id": "1", "text": "one"}]


def test_parse_fixture_uses_only_generic_fixture_keys() -> None:
    posts = parse_response(
        FIXTURE.read_text(encoding="utf-8"), group_id="fixture-group", salt="test-salt"
    )
    assert len(posts) == 2
    assert posts[0].post_id == "fixture-001"
    assert posts[0].text == "Bài viết fixture thứ nhất"
    assert posts[0].source == "playwright_graphql"
    assert posts[0].author_hash != "author-001"


def test_parse_does_not_guess_missing_id() -> None:
    payload = (
        '{"data":{"items":[{"text":"No identifier",'
        '"created_at":"2026-01-01T00:00:00+00:00"}]}}'
    )
    assert parse_response(payload, group_id="g1") == []
