"""CLI surface tests for Phase 3 to Phase 5 commands."""

import re

from typer.testing import CliRunner

from fbpipe.cli import app


def test_phase_3_and_4_commands_are_registered() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    for command in (
        "represent",
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
