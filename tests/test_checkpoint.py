from fbpipe.collect.checkpoint import Checkpoint


def test_checkpoint_round_trip(tmp_path) -> None:
    path = tmp_path / "checkpoint.json"
    checkpoint = Checkpoint(
        seen_ids={"p1", "p2"},
        scroll_count=4,
        last_created_at="2026-01-01T00:00:00+00:00",
        run_id="run-1",
    )
    checkpoint.save(path)
    restored = Checkpoint.load(path)
    assert restored.seen_ids == {"p1", "p2"}
    assert restored.scroll_count == 4
    assert restored.last_created_at == "2026-01-01T00:00:00+00:00"
    assert restored.run_id == "run-1"


def test_missing_checkpoint_is_empty(tmp_path) -> None:
    checkpoint = Checkpoint.load(tmp_path / "missing.json")
    assert checkpoint.seen_ids == set()
    assert checkpoint.scroll_count == 0


def test_seen_ids() -> None:
    checkpoint = Checkpoint(seen_ids=set())
    assert not checkpoint.has_seen("p1")
    checkpoint.mark_seen("p1")
    assert checkpoint.has_seen("p1")
