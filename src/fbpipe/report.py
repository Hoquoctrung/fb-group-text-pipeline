"""Generate an aggregate Markdown report without changing the manual report."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
_METRIC_KEYS = (
    "stage",
    "created_at",
    "input_path",
    "input_files",
    "n_documents",
    "n_raw",
    "n_raw_lines",
    "n_invalid_records",
    "n_after_dedup",
    "n_after_spam",
    "n_after_short",
    "n_kept",
    "n_duplicates",
    "n_spam",
    "n_short",
    "source_column_present",
    "source_counts",
    "length_distribution_tokens",
    "token_quality",
    "bow_dimensions",
    "tfidf_dimensions",
    "vocabulary_size",
    "e5_available",
    "e5_status",
    "proxy_labels",
    "n_samples",
    "n_labeled",
    "sqlite_count",
    "sqlite_size_bytes",
    "parquet_count",
    "parquet_size_bytes",
    "iterations",
    "pipeline_seconds",
    "ablation_seconds",
    "ratio_posts_without_diacritics",
    "ratio_posts_with_teencode",
    "ratio_code_mixed",
    "n_documents_requested",
    "dedup_method",
    "model",
)


def _compact(value: Any, *, limit: int = 220) -> str:
    """Render an aggregate value compactly; never expand full metric arrays."""
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(rendered) > limit:
        return rendered[: limit - 3] + "..."
    return rendered


def _read_metric(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "JSON root is not an object"
    return value, None


def _metric_entries(data: dict[str, Any]) -> list[tuple[str, Any]]:
    """Select concise aggregate fields without rendering long arrays or text."""
    entries = [(key, data[key]) for key in _METRIC_KEYS if key in data]
    if not entries:
        for key, value in data.items():
            if isinstance(value, str | int | float | bool) or value is None:
                entries.append((key, value))
            if len(entries) >= 12:
                break
    return entries


def _relative_link(path: Path, output_parent: Path) -> str:
    relative = Path(os.path.relpath(path.resolve(), output_parent.resolve()))
    return quote(relative.as_posix(), safe="/._-()")


def generate_report(
    *,
    metrics_dir: str | Path = "data/metrics",
    figures_dir: str | Path = "docs/figures",
    output_path: str | Path = "docs/REPORT_generated.md",
    manual_report_path: str | Path = "docs/REPORT.md",
) -> dict[str, Any]:
    """Write report output from aggregate JSON metrics and existing figure files.

    The manual ``docs/REPORT.md`` is a protected destination. This function is
    deliberately metric-only: it does not read or reproduce raw post text.
    """
    metrics_root = Path(metrics_dir)
    figures_root = Path(figures_dir)
    output = Path(output_path)
    manual = Path(manual_report_path)
    if output.resolve() == manual.resolve():
        raise ValueError(
            "Refusing to overwrite the manual report; use docs/REPORT_generated.md."
        )

    metric_files = sorted(metrics_root.glob("*.json")) if metrics_root.is_dir() else []
    metrics: list[tuple[Path, dict[str, Any]]] = []
    metric_errors: list[tuple[Path, str]] = []
    for path in metric_files:
        data, error = _read_metric(path)
        if data is None:
            metric_errors.append((path, error or "unknown JSON error"))
        else:
            metrics.append((path, data))

    allowed_suffixes = _IMAGE_SUFFIXES | {".pdf", ".html"}
    figure_files = (
        sorted(
            path
            for path in figures_root.iterdir()
            if path.is_file() and path.suffix.lower() in allowed_suffixes
        )
        if figures_root.is_dir()
        else []
    )

    lines = [
        "# Báo cáo tự động — FB Group Text Pipeline",
        "",
        (
            "> Tệp này được sinh từ `data/metrics/*.json` và danh sách hình trong "
            "`docs/figures/`. Lệnh `fbpipe report` không sửa hoặc ghi đè "
            "`docs/REPORT.md`."
        ),
        "",
        f"- Thời điểm sinh (UTC): `{datetime.now(UTC).isoformat(timespec='seconds')}`",
        f"- Thư mục metrics: `{metrics_root.as_posix()}`",
        f"- Thư mục hình: `{figures_root.as_posix()}`",
        f"- Số tệp metrics đọc được: **{len(metrics)}**",
        f"- Số hình/đầu ra đồ họa liệt kê được: **{len(figure_files)}**",
        "",
        "## Nguồn dữ liệu và giới hạn diễn giải",
        "",
    ]

    source_counts: dict[str, int] | None = None
    ordered_metrics = sorted(
        metrics,
        key=lambda item: (item[0].name != "analyze.json", item[0].name),
    )
    for _path, data in ordered_metrics:
        candidate = data.get("source_counts")
        if isinstance(candidate, dict):
            source_counts = {
                str(key): int(value)
                for key, value in candidate.items()
                if isinstance(value, int | float) and not isinstance(value, bool)
            }
            if source_counts:
                break
    if source_counts:
        lines.extend(
            [
                (
                    "Phân bố nguồn lấy từ trường `source_counts` của metrics "
                    "(không tự suy luận nguồn nếu metrics không cung cấp):"
                ),
                "",
                "| Nguồn | Số bản ghi |",
                "|---|---:|",
            ]
        )
        for source, count in sorted(source_counts.items()):
            lines.append(f"| `{source}` | {count} |")
    else:
        lines.append(
            "Metrics hiện có không cung cấp `source_counts`; báo cáo không suy "
            "đoán rằng dữ liệu là bài Facebook thật. Hãy chạy `fbpipe analyze` "
            "trên Silver có cột `source` để bổ sung phân bố nguồn."
        )
    lines.extend(
        [
            "",
            (
                "Các bản ghi `synthetic` và các dòng benchmark nhân bản chỉ dùng "
                "kiểm thử/đo kỹ thuật; không được trình bày như dữ liệu Facebook "
                "thật. Metrics không thay thế việc duyệt dữ liệu nguồn hoặc kiểm "
                "tra quyền thu thập."
            ),
            "",
            "## Tóm tắt metrics",
            "",
        ]
    )

    if not metrics and not metric_errors:
        lines.append(
            "Chưa tìm thấy tệp JSON trong thư mục metrics. Chạy các stage cần "
            "thiết trước `fbpipe report`."
        )

    for path, data in metrics:
        stage = data.get("stage") or path.stem
        lines.extend([f"### `{path.name}` — {stage}", ""])
        entries = _metric_entries(data)
        if entries:
            lines.extend(["| Trường | Giá trị |", "|---|---|"])
            for key, value in entries:
                lines.append(f"| `{key}` | `{_compact(value)}` |")
        else:
            lines.append("Tệp metrics không có trường tổng hợp để hiển thị.")
        if data.get("proxy_labels") is True:
            lines.extend(
                [
                    "",
                    (
                        "> **Cảnh báo nhãn:** `proxy_labels=true`. Các điểm số này "
                        "chỉ là chẩn đoán trên nhãn yếu theo luật, không phải "
                        "đánh giá ground truth."
                    ),
                ]
            )
        if path.stem == "bench_storage" or data.get("is_benchmark_clone") is True:
            lines.extend(
                [
                    "",
                    (
                        "> **Cảnh báo benchmark:** các dòng benchmark là bản ghi "
                        "nhân bản; không tính như số bài độc lập từ nguồn."
                    ),
                ]
            )
        lines.append("")

    if metric_errors:
        lines.extend(["### Metrics không đọc được", ""])
        for path, error in metric_errors:
            safe_error = error.replace("`", "'")
            lines.append(f"- `{path.name}`: `{safe_error}`")
        lines.append("")

    lines.extend(["## Danh sách hình đã có", ""])
    if not figure_files:
        lines.append(
            "Chưa có hình trong thư mục đã cấu hình. Chạy `fbpipe analyze` rồi "
            "`fbpipe viz`."
        )
    else:
        for figure in figure_files:
            link = _relative_link(figure, output.parent)
            lines.append(f"- [{figure.name}]({link})")
        image_files = [
            path for path in figure_files if path.suffix.lower() in _IMAGE_SUFFIXES
        ]
        if image_files:
            lines.extend(["", "### Hình", ""])
            for figure in image_files:
                link = _relative_link(figure, output.parent)
                lines.extend(
                    [f"#### {figure.stem}", "", f"![{figure.name}]({link})", ""]
                )

    lines.extend(
        [
            "## Nhận định của người nghiên cứu",
            "",
            (
                "<!-- TRUNG VIẾT: Kiểm tra từng hình và bổ sung nhận định có "
                "bằng chứng. Không suy rộng từ dữ liệu synthetic hoặc proxy "
                "labels. -->"
            ),
            "",
            "## Tái lập",
            "",
            (
                "Chạy `fbpipe analyze`, `fbpipe viz`, rồi `fbpipe report` sau khi "
                "metrics và hình đã được cập nhật. Báo cáo chỉ phản ánh các tệp "
                "tại thời điểm sinh."
            ),
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return {
        "output_path": str(output),
        "metrics_count": len(metrics),
        "metrics_errors": len(metric_errors),
        "figure_count": len(figure_files),
        "source_counts": source_counts or {},
    }
