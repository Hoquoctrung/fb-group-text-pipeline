"""CLI surface tests for Phase 3 to Phase 5 commands."""

import json
import re
from pathlib import Path

from typer.testing import CliRunner

import fbpipe.cli as cli
from fbpipe.cli import app


def test_phase_3_and_4_commands_are_registered() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    for command in (
        "represent",
        "demo",
        "analyze",
        "viz",
        "label-sample",
        "label-eval",
        "store",
        "bench-storage",
    ):
        assert command in result.output


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain(text: str) -> str:
    """Strip ANSI escape codes from terminal output."""
    return ANSI_RE.sub("", text)


def test_represent_help_documents_optional_e5() -> None:
    result = CliRunner().invoke(
        app,
        ["represent", "--help"],
        color=False,
        env={
            "COLUMNS": "160",
            "TERMINAL_WIDTH": "160",
            "NO_COLOR": "1",
        },
    )

    output = _plain(result.output)
    assert result.exit_code == 0, output
    assert "--skip-e5" in output, output
    assert "--force" in output, output


def test_demo_runs_all_offline_stages_and_prints_f06_terms(
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, check: bool, timeout: float) -> None:
        assert check is True
        assert timeout > 0
        args = tuple(command[3:])
        calls.append(args)
        if args and args[0] == "analyze":
            metrics_path = tmp_path / "data" / "demo" / "metrics" / "analyze.json"
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(
                json.dumps(
                    {
                        "top_tf_terms": [{"term": "người", "count": 7}],
                        "top_tfidf_terms": [{"term": "thông_tin", "mean_tfidf": 0.25}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    default_config_content = Path("configs/default.yaml").read_text(encoding="utf-8")
    (tmp_path / "configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs" / "default.yaml").write_text(
        default_config_content, encoding="utf-8"
    )

    existing_import = tmp_path / "data" / "bronze" / "my_import.jsonl"
    existing_import.parent.mkdir(parents=True, exist_ok=True)
    existing_import.write_text("{}\n", encoding="utf-8")
    stale_demo = tmp_path / "data" / "demo" / "stale.jsonl"
    stale_demo.parent.mkdir(parents=True, exist_ok=True)
    stale_demo.write_text("{}\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    result = CliRunner().invoke(app, ["demo"])

    assert result.exit_code == 0, result.output
    assert calls == list(
        cli._build_demo_steps(
            Path("data/demo-config.yaml"),
            Path("data/demo"),
        )
    )
    assert calls[0][:3] == ("synth", "--n", "200")
    assert "--skip-e5" in calls[2]
    assert "--force" in calls[2]
    assert existing_import.exists()
    assert not stale_demo.exists()
    assert "người: 7" in result.output
    assert "thông_tin: 0.25" in result.output
    assert "target: under 90s" in result.output
