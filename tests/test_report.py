"""Fast unit tests for generated-report input handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fbpipe.report import generate_report


def test_report_summarizes_metrics_and_existing_figures(tmp_path: Path) -> None:
    metrics_dir = tmp_path / "data" / "metrics"
    figures_dir = tmp_path / "docs" / "figures"
    output_path = tmp_path / "docs" / "REPORT_generated.md"
    metrics_dir.mkdir(parents=True)
    figures_dir.mkdir(parents=True)
    (metrics_dir / "analyze.json").write_text(
        json.dumps(
            {
                "stage": "analyze",
                "n_documents": 3,
                "source_counts": {"synthetic": 2, "import": 1},
            }
        ),
        encoding="utf-8",
    )
    (metrics_dir / "label_eval.json").write_text(
        json.dumps({"stage": "label_eval", "proxy_labels": True}),
        encoding="utf-8",
    )
    (figures_dir / "F01_daily_posts.png").write_bytes(b"fixture")
    (figures_dir / "F09_lda_coherence.png").write_bytes(b"fixture")
    (figures_dir / "F11_embedding_map.png").write_bytes(b"fixture")

    result = generate_report(
        metrics_dir=metrics_dir,
        figures_dir=figures_dir,
        output_path=output_path,
        manual_report_path=tmp_path / "docs" / "REPORT.md",
    )
    report = output_path.read_text(encoding="utf-8")

    assert result["metrics_count"] == 2
    assert result["figure_count"] == 3
    assert "synthetic" in report
    assert "proxy_labels=true" in report
    assert "F01_daily_posts.png" in report
    assert "F09_lda_coherence.png" in report
    assert "F11_embedding_map.png" in report


def test_report_refuses_manual_report_destination(tmp_path: Path) -> None:
    manual_report = tmp_path / "docs" / "REPORT.md"
    manual_report.parent.mkdir(parents=True)
    manual_report.write_text("manual", encoding="utf-8")

    with pytest.raises(ValueError, match="Refusing to overwrite"):
        generate_report(
            metrics_dir=tmp_path / "metrics",
            figures_dir=tmp_path / "figures",
            output_path=manual_report,
            manual_report_path=manual_report,
        )

    assert manual_report.read_text(encoding="utf-8") == "manual"


def test_report_handles_missing_directories_and_invalid_json(tmp_path: Path) -> None:
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    (metrics_dir / "broken.json").write_text("{not-json", encoding="utf-8")
    output_path = tmp_path / "docs" / "REPORT_generated.md"

    result = generate_report(
        metrics_dir=metrics_dir,
        figures_dir=tmp_path / "no-figures",
        output_path=output_path,
        manual_report_path=tmp_path / "docs" / "REPORT.md",
    )
    report = output_path.read_text(encoding="utf-8")

    assert result["metrics_errors"] == 1
    assert result["figure_count"] == 0
    assert "broken.json" in report
    assert "Chưa có hình" in report
