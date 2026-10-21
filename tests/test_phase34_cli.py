"""CLI surface tests for Phase 3 to Phase 5 commands."""

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


def test_represent_help_documents_optional_e5() -> None:
    result = CliRunner().invoke(
        app,
        ["represent", "--help"],
        env={
            "COLUMNS": "160",
            "TERMINAL_WIDTH": "160",
            "NO_COLOR": "1",
        },
    )
    assert result.exit_code == 0, result.output
    assert "--skip-e5" in result.output
    assert "--force" in result.output
