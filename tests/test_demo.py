"""Unit tests for the offline demo orchestrator."""

from __future__ import annotations

import subprocess
import sys

import fbpipe.cli as cli
from typer.testing import CliRunner

from fbpipe.cli import app


def test_demo_runs_the_required_offline_stages(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool,
        env: dict[str, str],
        timeout: float,
    ) -> None:
        assert check is True
        calls.append((command, {"env": env, "timeout": timeout}))

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    result = CliRunner().invoke(app, ["demo"])

    assert result.exit_code == 0, result.output
    stage_commands = [call[0][3] for call in calls]
    assert stage_commands == [
        "synth",
        "preprocess",
        "represent",
        "store",
        "analyze",
        "viz",
        "report",
    ]
    assert calls[0][0][4:] == [
        "--n",
        "200",
        "--output",
        "data/bronze/demo/synthetic.jsonl",
    ]
    assert "--input-dir" in calls[1][0]
    assert "data/bronze/demo" in calls[1][0]
    assert "--skip-e5" in calls[2][0]
    assert all(call[1]["env"]["HF_HUB_OFFLINE"] == "1" for call in calls)
    assert all(call[1]["env"]["TRANSFORMERS_OFFLINE"] == "1" for call in calls)
    assert "[demo] COMPLETED" in result.output
    assert "target < 90 seconds" in result.output


def test_demo_stops_when_a_stage_fails(monkeypatch) -> None:
    def fail_represent(
        command: list[str],
        *,
        check: bool,
        env: dict[str, str],
        timeout: float,
    ) -> None:
        if command[3] == "represent":
            raise subprocess.CalledProcessError(4, command)

    monkeypatch.setattr(cli.subprocess, "run", fail_represent)
    result = CliRunner().invoke(app, ["demo"])

    assert result.exit_code == 4
    assert "[demo] FAILED represent" in result.output
    assert "[demo] COMPLETED" not in result.output
