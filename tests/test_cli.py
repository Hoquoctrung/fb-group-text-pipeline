# path: tests/test_cli.py

import pytest
import typer

from fbpipe.cli import _validate_crawl_state


def test_fresh_crawl_allowed_without_existing_state(tmp_path) -> None:
    _validate_crawl_state(
        resume=False,
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=tmp_path / "raw_posts.jsonl",
    )


def test_resume_requires_both_existing_files(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    output = tmp_path / "raw_posts.jsonl"
    checkpoint.write_text("{}", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="requires both"):
        _validate_crawl_state(
            resume=True,
            checkpoint_path=checkpoint,
            output_path=output,
        )


def test_resume_allowed_when_both_files_exist(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    output = tmp_path / "raw_posts.jsonl"
    checkpoint.write_text("{}", encoding="utf-8")
    output.write_text("", encoding="utf-8")

    _validate_crawl_state(
        resume=True,
        checkpoint_path=checkpoint,
        output_path=output,
    )


def test_fresh_crawl_refuses_existing_state(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    output = tmp_path / "raw_posts.jsonl"
    checkpoint.write_text("{}", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="Existing crawl state"):
        _validate_crawl_state(
            resume=False,
            checkpoint_path=checkpoint,
            output_path=output,
        )
