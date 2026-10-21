import json

from fbpipe.collect.import_collector import ImportCollector


def test_import_jsonl_and_scrub_pii(tmp_path) -> None:
    path = tmp_path / "posts.jsonl"
    path.write_text(
        json.dumps(
            {
                "post_id": "p1",
                "author": "user-1",
                "created_at": "2026-01-01T10:00:00+00:00",
                "text": "Hello test@example.com",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    posts = list(ImportCollector(path, group_id="g1", salt="test-salt").iter_posts())
    assert len(posts) == 1
    assert posts[0].post_id == "p1"
    assert posts[0].group_id == "g1"
    assert "<EMAIL>" in posts[0].text
    assert posts[0].source == "import"
    assert posts[0].author_hash != "user-1"


def test_import_csv(tmp_path) -> None:
    path = tmp_path / "posts.csv"
    path.write_text(
        "post_id,author,created_at,text\np1,user-1,2026-01-01T10:00:00+00:00,Hello\n",
        encoding="utf-8",
    )
    posts = list(ImportCollector(path, group_id="g1", salt="test-salt").iter_posts())
    assert len(posts) == 1
    assert posts[0].post_id == "p1"


def test_import_skips_invalid_row_and_reports_error(tmp_path) -> None:
    path = tmp_path / "posts.jsonl"
    path.write_text(
        '{"post_id":"p1","author":"u","text":""}\n'
        '{"post_id":"p2","author":"u","text":"valid"}\n',
        encoding="utf-8",
    )
    collector = ImportCollector(path, group_id="g1", salt="test-salt")
    posts = list(collector.iter_posts())
    assert len(posts) == 1
    assert len(collector.errors) == 1
    assert "text is required" in collector.errors[0]


def test_import_requires_salt_for_author_hashing(tmp_path) -> None:
    path = tmp_path / "posts.csv"
    path.write_text("author,text\nu,hello\n", encoding="utf-8")
    collector = ImportCollector(path, group_id="g1", salt="")
    posts = list(collector.iter_posts())
    assert posts == []
    assert "FBPIPE_SALT is required" in collector.errors[0]
