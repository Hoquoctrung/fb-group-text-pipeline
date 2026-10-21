"""Command-line interface for fb-group-text-pipeline."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
import yaml
from dotenv import load_dotenv

from fbpipe.analysis import analyze_corpus
from fbpipe.collect.import_collector import ImportCollector
from fbpipe.collect.playwright_collector import (
    CollectionBlocked,
    PlaywrightCollector,
)
from fbpipe.collect.playwright_collector import (
    auth as browser_auth,
)
from fbpipe.collect.synthetic import SyntheticCollector
from fbpipe.config import load_config
from fbpipe.logging_utils import configure_logging
from fbpipe.metrics import write_metrics
from fbpipe.preprocess.pipeline import preprocess_corpus
from fbpipe.report import generate_report
from fbpipe.represent.labeling import evaluate_labels, sample_label_file
from fbpipe.represent.pipeline import represent_corpus
from fbpipe.storage.benchmark import benchmark_storage
from fbpipe.storage.parquet_store import ParquetStore
from fbpipe.storage.sqlite_store import SQLiteStore
from fbpipe.viz import generate_figures

if TYPE_CHECKING:
    from playwright.sync_api import Response

load_dotenv()

app = typer.Typer(
    name="fbpipe",
    help="Authorized, reproducible Facebook group text pipeline.",
    no_args_is_help=True,
)


def _write_jsonl(posts: Any, output: Path, *, append: bool = False) -> int:
    """Write posts as newline-delimited JSON and return the count."""
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    mode = "a" if append else "w"
    with output.open(mode, encoding="utf-8") as handle:
        for post in posts:
            handle.write(post.model_dump_json(exclude_none=False) + "\n")
            handle.flush()
            count += 1
    return count


@app.command("auth")
def auth_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
) -> None:
    """Open a visible browser for manual login and save local state."""
    configure_logging()
    cfg = load_config(config)
    browser_auth(url=cfg.group.url, state_path=".auth/state.json")
    typer.echo("Authentication state saved locally to .auth/state.json")


def _anonymize_probe_value(value: Any, counter: dict[str, int], key: str = "") -> Any:
    """Anonymize common identifier/name/text fields while retaining JSON shape.

    This is a conservative heuristic, not a guarantee that arbitrary HTML or
    all personal data is anonymized. Review probe artifacts before sharing.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for child_key, child_value in value.items():
            normalized = child_key.lower()
            if normalized in {"id", "author_id", "owner_id", "user_id", "actor_id"}:
                counter["id"] += 1
                result[child_key] = (
                    f"ID_{counter['id']}" if child_value is not None else None
                )
            elif normalized in {"name", "full_name", "username"}:
                counter["name"] += 1
                result[child_key] = (
                    f"NAME_{counter['name']}" if child_value is not None else None
                )
            elif normalized in {"text", "message", "content", "body"} and isinstance(
                child_value, str
            ):
                counter["text"] += 1
                result[child_key] = f"REDACTED_TEXT_{counter['text']}"
            else:
                result[child_key] = _anonymize_probe_value(
                    child_value, counter, child_key
                )
        return result
    if isinstance(value, list):
        return [_anonymize_probe_value(item, counter, key) for item in value]
    if isinstance(value, str):
        from fbpipe.privacy import scrub_pii

        return scrub_pii(value)
    return value


def _key_paths(
    value: Any, prefix: str = "$", result: set[str] | None = None
) -> set[str]:
    """Collect structural JSON paths without copying personal values."""
    if result is None:
        result = set()
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            result.add(child_path)
            _key_paths(child, child_path, result)
    elif isinstance(value, list):
        for child in value:
            _key_paths(child, f"{prefix}[]", result)
    return result


@app.command("probe")
def probe_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    max_samples: int = typer.Option(5, min=1, max=10),
    scrolls: int = typer.Option(3, min=1, max=6),
) -> None:
    """Capture a few passively observed responses and anonymize JSON structure."""
    configure_logging()
    cfg = load_config(config)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise typer.BadParameter(
            "Install Playwright with `pip install -e '.[crawl]'`."
        ) from exc
    state_path = Path(".auth/state.json")
    if not state_path.exists():
        raise typer.BadParameter("Missing .auth/state.json; run `fbpipe auth` first.")

    responses: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()

        def handle_response(response: Response) -> None:
            if "/api/graphql" not in response.url:
                return
            try:
                responses.append(response.body().decode("utf-8", errors="replace"))
            except Exception:
                return

        page.on("response", handle_response)
        try:
            page.goto(cfg.group.url, wait_until="domcontentloaded")
            for _ in range(scrolls):
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(int(cfg.compliance.delay_seconds[0] * 1000))
                if len(responses) >= max_samples:
                    break
        finally:
            browser.close()

    debug_dir = Path("debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    sample_path = debug_dir / "probe_samples.jsonl"
    paths: set[str] = set()
    saved = 0
    counters: defaultdict[str, int] = defaultdict(int)
    with sample_path.open("w", encoding="utf-8") as handle:
        for payload in responses[:max_samples]:
            try:
                from fbpipe.collect.graphql_parser import iter_json_values

                values = list(iter_json_values(payload))
            except (ValueError, json.JSONDecodeError):
                continue
            for value in values:
                paths.update(_key_paths(value))
                safe_value = _anonymize_probe_value(value, counters)
                handle.write(json.dumps(safe_value, ensure_ascii=False) + "\n")
                saved += 1
    report_path = debug_dir / "probe_report.md"
    report = [
        "# Probe report (heuristically anonymized)",
        "",
        f"- Captured GraphQL-like responses: {len(responses)}",
        f"- JSON values saved after parsing: {saved}",
        "- HTML/DOM snapshot: not captured in the 48-hour scope.",
        (
            "- Status: TODO(real-sample) — inspect this report and samples "
            "before modifying the parser."
        ),
        (
            "- Warning: anonymization is heuristic; manually review before "
            "sharing or committing."
        ),
        "",
        "## Observed JSON paths",
        "",
    ]
    report.extend(f"- `{path}`" for path in sorted(paths))
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    typer.echo(f"Saved {saved} anonymized-shape JSON values to {sample_path}")
    typer.echo(f"Saved observed key paths to {report_path}")


@app.command("synth")
def synth_command(
    n: int = typer.Option(100, "--n", min=1),
    output: Path = typer.Option(Path("data/bronze/synthetic.jsonl"), "--output"),
    seed: int = typer.Option(42, "--seed"),
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
) -> None:
    """Generate deterministic synthetic Bronze posts."""
    configure_logging()
    cfg = load_config(config)
    posts = SyntheticCollector(n=n, seed=seed).iter_posts()
    count = _write_jsonl(posts, output)
    write_metrics(
        "synthetic",
        {"records": count, "seed": seed, "output": str(output)},
        cfg.project.data_dir,
    )
    typer.echo(f"Generated {count} synthetic posts -> {output}")


@app.command("import")
def import_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(Path("data/bronze/imported.jsonl"), "--output"),
    group_id: str = typer.Option("230048322891238", "--group-id"),
) -> None:
    """Import an allowed JSONL/CSV dataset into Bronze."""
    configure_logging()
    collector = ImportCollector(
        input_path, group_id=group_id, salt=os.getenv("FBPIPE_SALT")
    )
    count = _write_jsonl(collector.iter_posts(), output)
    write_metrics(
        "import",
        {
            "records": count,
            "errors": collector.errors,
            "input": str(input_path),
            "output": str(output),
        },
    )
    typer.echo(
        f"Imported {count} posts; skipped {len(collector.errors)} "
        f"invalid rows -> {output}"
    )


def _validate_crawl_state(
    *,
    resume: bool,
    checkpoint_path: Path,
    output_path: Path,
) -> None:
    """Validate existing files before starting or resuming a crawl."""
    checkpoint_exists = checkpoint_path.exists()
    output_exists = output_path.exists()
    if resume and not (checkpoint_exists and output_exists):
        raise typer.BadParameter(
            "--resume requires both an existing checkpoint and Bronze JSONL file."
        )
    if not resume and (checkpoint_exists or output_exists):
        raise typer.BadParameter(
            "Existing crawl state found. Use --resume to continue, or archive "
            "the existing checkpoint and output before starting a new crawl."
        )


@app.command("crawl")
def crawl_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Resume an existing crawl using its checkpoint and Bronze output.",
    ),
) -> None:
    """Collect via passive browser responses, stopping on restrictions."""
    configure_logging()
    cfg = load_config(config)
    if not cfg.compliance.acknowledged:
        raise typer.BadParameter(
            "Review docs/ETHICS.md and obtain authorization, then explicitly set "
            "compliance.acknowledged=true in the config."
        )
    if not os.getenv("FBPIPE_SALT"):
        raise typer.BadParameter(
            "FBPIPE_SALT is required; configure it in your local .env."
        )

    bronze_dir = Path(cfg.project.data_dir) / "bronze"
    output = bronze_dir / "raw_posts.jsonl"
    checkpoint_path = bronze_dir / "checkpoint.json"
    _validate_crawl_state(
        resume=resume,
        checkpoint_path=checkpoint_path,
        output_path=output,
    )

    collector = PlaywrightCollector(
        url=cfg.group.url,
        group_id=cfg.group.id,
        state_path=".auth/state.json",
        checkpoint_path=checkpoint_path,
        data_path=output,
        headless=cfg.collect.headless,
        max_posts=cfg.compliance.max_posts_per_session,
        max_minutes=cfg.compliance.max_session_minutes,
        delay_range=cfg.compliance.delay_seconds,
        empty_scroll_limit=cfg.collect.stop_after_empty_scrolls,
        seed=cfg.project.seed,
        resume=resume,
    )
    try:
        count = _write_jsonl(collector.iter_posts(), output, append=resume)
    except CollectionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    write_metrics(
        "crawl",
        {
            "records": count,
            "group_id": cfg.group.id,
            "output": str(output),
            "resumed": resume,
        },
        cfg.project.data_dir,
    )
    typer.echo(f"Collected {count} new posts -> {output}")


@app.command("preprocess")
def preprocess_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_dir: Path | None = typer.Option(None, "--input-dir"),
    output: Path | None = typer.Option(None, "--output"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Run S0-S11 preprocessing and write Silver Parquet plus metrics."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    source_dir = input_dir or data_dir / "bronze"
    output_path = output or data_dir / "silver" / "documents.parquet"
    try:
        result = preprocess_corpus(
            input_dir=source_dir,
            output_path=output_path,
            data_dir=data_dir,
            resource_dir=Path("resources"),
            settings=cfg.preprocess,
            force=force,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4 if isinstance(exc, RuntimeError) else 2) from exc
    if result.skipped_as_up_to_date:
        typer.echo(f"Preprocess is up to date: {result.output_path}")
        return
    typer.echo(
        f"Preprocessed {result.raw_records} posts -> {result.output_path}; "
        f"invalid records: {result.invalid_records}; metrics: {result.metrics_path}"
    )


@app.command("analyze")
def analyze_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
) -> None:
    """Summarize Silver data and write fast analysis metrics without loading E5."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    source_path = input_path or data_dir / "silver" / "documents.parquet"
    try:
        result = analyze_corpus(input_path=source_path, data_dir=data_dir)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"Analyzed {result['n_documents']} documents -> "
        f"{result['metrics_path']}; source={result['source_counts']}"
    )


@app.command("viz")
def viz_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
    output_dir: Path = typer.Option(Path("docs/figures"), "--output-dir"),
) -> None:
    """Generate matplotlib figures F01/F03/F06/F07/F09/F10/F11/F13/F14/F15."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    source_path = input_path or data_dir / "silver" / "documents.parquet"
    try:
        generated = generate_figures(
            input_path=source_path,
            data_dir=data_dir,
            output_dir=output_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    typer.echo(f"Generated {len(generated)} matplotlib figures -> {output_dir}")
    for figure in generated:
        typer.echo(f"- {figure}")


@app.command("report")
def report_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    metrics_dir: Path | None = typer.Option(None, "--metrics-dir"),
    figures_dir: Path = typer.Option(Path("docs/figures"), "--figures-dir"),
    output: Path = typer.Option(Path("docs/REPORT_generated.md"), "--output"),
) -> None:
    """Generate metrics report without replacing the manual report."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    selected_metrics_dir = metrics_dir or data_dir / "metrics"
    try:
        result = generate_report(
            metrics_dir=selected_metrics_dir,
            figures_dir=figures_dir,
            output_path=output,
            manual_report_path=Path("docs/REPORT.md"),
        )
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"Generated {result['output_path']}; metrics={result['metrics_count']} "
        f"(errors={result['metrics_errors']}), figures={result['figure_count']}"
    )


@app.command("represent")
def represent_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    skip_e5: bool = typer.Option(
        False,
        "--skip-e5",
        help="Skip the optional E5 model.",
    ),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Write BoW/TF-IDF matrices and attempt optional E5 embeddings."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    source = input_path or data_dir / "silver" / "documents.parquet"
    destination = output_dir or data_dir / "gold"
    try:
        result = represent_corpus(
            input_path=source,
            output_dir=destination,
            data_dir=data_dir,
            settings=cfg.represent,
            include_e5=not skip_e5,
            force=force,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except ImportError as exc:
        typer.echo(f"Required representation dependency is missing: {exc}", err=True)
        raise typer.Exit(code=4) from exc
    typer.echo(
        f"Represented {result.get('n_documents', '?')} documents -> {destination}; "
        f"BoW={result.get('bow', {}).get('dimensions', 0)} dims; "
        f"TF-IDF={result.get('tfidf', {}).get('dimensions', 0)} dims; "
        "E5="
        + (
            "available"
            if result.get("e5", {}).get("available")
            else "skipped/unavailable"
        )
        + (" (up to date)" if result.get("skipped_as_up_to_date") else "")
    )


@app.command("label-sample")
def label_sample_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
    output_path: Path | None = typer.Option(None, "--output"),
    n: int = typer.Option(200, "--n", min=1),
    seed: int = typer.Option(42, "--seed"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Create a stratified CSV template for human labeling."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    try:
        result = sample_label_file(
            input_path=input_path or data_dir / "silver" / "documents.parquet",
            output_path=output_path or data_dir / "labels" / "to_label.csv",
            n=n,
            seed=seed if seed is not None else cfg.project.seed,
            force=force,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    write_metrics("label_sample", result, data_dir)
    typer.echo(
        f"Created {result['sampled_n']} label rows -> {result['output_path']}; "
        "fill the `label` column manually before label-eval."
    )
    typer.echo("Taxonomy: " + ", ".join(result["taxonomy"]))


@app.command("label-eval")
def label_eval_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
    labels_path: Path | None = typer.Option(None, "--labels"),
    represent_dir: Path | None = typer.Option(None, "--represent-dir"),
) -> None:
    """Evaluate feature matrices; clearly mark rule-based labels as proxy labels."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    try:
        result = evaluate_labels(
            input_path=input_path or data_dir / "silver" / "documents.parquet",
            labels_path=labels_path or data_dir / "labels" / "to_label.csv",
            represent_dir=represent_dir or data_dir / "gold",
            data_dir=data_dir,
            seed=cfg.project.seed,
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"Evaluated {result['n_labeled']} labels; "
        f"proxy_labels={str(result['proxy_labels']).lower()}; "
        f"metrics: {data_dir / 'metrics' / 'label_eval.json'}"
    )
    for name, details in result["results"].items():
        score = details.get("macro_f1")
        typer.echo(f"{name}: macro-F1={score if score is not None else 'n/a'}")


def _sqlite_path_from_config(storage_settings: dict[str, Any], data_dir: Path) -> Path:
    """Resolve the configured SQLite URL or a simple relative file path."""
    configured = str(
        storage_settings.get(
            "sqlite_path",
            storage_settings.get("sqlite_url", "sqlite:///data/fbpipe.db"),
        )
    )
    if configured.startswith("sqlite:///"):
        configured = configured.removeprefix("sqlite:///")
    path = Path(configured)
    return path if path.is_absolute() else Path.cwd() / path


@app.command("store")
def store_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
    sqlite_path: Path | None = typer.Option(None, "--sqlite-path"),
    parquet_output: Path | None = typer.Option(None, "--parquet-output"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Upsert Silver documents into SQLite/FTS5 and persist a Parquet copy."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    source = input_path or data_dir / "silver" / "documents.parquet"
    store_settings = cfg.storage
    database_path = sqlite_path or _sqlite_path_from_config(store_settings, data_dir)
    parquet_path = parquet_output or Path(
        store_settings.get("parquet_path", data_dir / "store" / "documents.parquet")
    )
    if not source.exists():
        typer.echo(
            f"Missing Silver Parquet: {source}; run `fbpipe preprocess` first.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        import pandas as pd

        frame = pd.read_parquet(source)
        sqlite_store = SQLiteStore(database_path)
        sqlite_store.init(reset=force)
        records = cast(
            list[dict[str, Any]],
            frame.to_dict(orient="records"),
        )
        upserted = sqlite_store.upsert_documents(records)
        parquet_store = ParquetStore(parquet_path)
        parquet_is_current = (
            parquet_path.exists()
            and not force
            and parquet_path.stat().st_mtime_ns >= source.stat().st_mtime_ns
        )
        if parquet_is_current:
            parquet_count = parquet_store.count()
            parquet_action = "skipped_up_to_date"
        else:
            parquet_count = parquet_store.write(frame, force=parquet_path.exists())
            parquet_action = "written"
    except (ImportError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    metrics = {
        "input_path": str(source),
        "sqlite_path": str(database_path),
        "sqlite_count": sqlite_store.count(),
        "sqlite_upserted_rows": upserted,
        "sqlite_size_bytes": sqlite_store.file_size_bytes(),
        "sqlite_full_text_search": "FTS5",
        "parquet_path": str(parquet_path),
        "parquet_count": parquet_count,
        "parquet_action": parquet_action,
        "parquet_size_bytes": parquet_store.file_size_bytes(),
    }
    write_metrics("store", metrics, data_dir)
    typer.echo(
        f"Stored {len(frame)} Silver rows; "
        f"SQLite={metrics['sqlite_count']} ({database_path}); "
        f"Parquet={parquet_count} ({parquet_path}, {parquet_action})."
    )


@app.command("bench-storage")
def bench_storage_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", exists=True),
    input_path: Path | None = typer.Option(None, "--input"),
    n: int = typer.Option(1000, "--n", min=1),
    iterations: int = typer.Option(20, "--iterations", min=2, max=100),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Benchmark SQLite FTS5 and Parquet scans on a seeded 1k-row bootstrap."""
    configure_logging()
    cfg = load_config(config)
    data_dir = Path(cfg.project.data_dir)
    source = input_path or data_dir / "silver" / "documents.parquet"
    if not source.exists():
        typer.echo(
            f"Missing Silver Parquet: {source}; run `fbpipe preprocess` first.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        import pandas as pd

        frame = pd.read_parquet(source)
        metrics = benchmark_storage(
            frame, n=n, seed=cfg.project.seed, iterations=iterations
        )
    except (ImportError, RuntimeError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4 if isinstance(exc, ImportError) else 2) from exc
    output_path = output or data_dir / "metrics" / "bench_storage.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    typer.echo(
        f"Benchmarked {metrics['n_documents']} cloned rows "
        f"({iterations} iterations) -> {output_path}; "
        f"SQLite FTS5 + Parquet. Clones are marked in metrics."
    )





def _build_demo_steps(
    config_path: Path,
    demo_dir: Path,
) -> tuple[tuple[str, ...], ...]:
    """Return the ordered CLI calls for an isolated synthetic-only run."""
    config_arg = str(config_path)
    return (
        (
            "synth",
            "--n",
            "200",
            "--output",
            str(demo_dir / "bronze" / "synthetic.jsonl"),
            "--config",
            config_arg,
        ),
        ("preprocess", "--config", config_arg, "--force"),
        ("represent", "--config", config_arg, "--skip-e5", "--force"),
        (
            "label-eval",
            "--config",
            config_arg,
            "--labels",
            str(demo_dir / "labels" / "no_human_labels_for_demo.csv"),
        ),
        ("store", "--config", config_arg, "--force"),
        ("analyze", "--config", config_arg),
        ("viz", "--config", config_arg),
        ("report", "--config", config_arg),
    )



def _print_demo_top_terms(metrics_path: Path, *, limit: int = 15) -> None:
    """Print top terms used by F06 from the most recent analysis metrics."""
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Cannot read F06 term metrics from {metrics_path}: {exc}"
        ) from exc

    for key, title, score_key in (
        ("top_tf_terms", "F06 — top 15 TF tokens", "count"),
        ("top_tfidf_terms", "F06 — top 15 TF-IDF tokens", "mean_tfidf"),
    ):
        rows = metrics.get(key, [])
        typer.echo(f"\n{title}")
        if not isinstance(rows, list) or not rows:
            typer.echo("  (không có token)")
            continue
        for rank, row in enumerate(rows[:limit], start=1):
            term = str(row.get("term", "?"))
            score = row.get(score_key, 0)
            typer.echo(f"  {rank:>2}. {term}: {score}")


@app.command("demo")
def demo_command() -> None:
    """Run the offline 200-post synthetic pipeline and print elapsed times."""
    configure_logging()
    started = time.perf_counter()
    demo_dir = Path("data/demo")
    shutil.rmtree(demo_dir, ignore_errors=True)
    config_path = Path("data/demo-config.yaml")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    raw_config = yaml.safe_load(
        Path("configs/default.yaml").read_text(encoding="utf-8")
    )
    raw_config["project"]["data_dir"] = str(demo_dir)
    raw_config["storage"]["sqlite_url"] = f"sqlite:///{demo_dir.as_posix()}/fbpipe.db"
    raw_config["storage"]["parquet_path"] = str(
        demo_dir / "store" / "documents.parquet"
    )
    config_path.write_text(
        yaml.safe_dump(raw_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    typer.echo(
        "fbpipe demo: 200 synthetic posts; E5 skipped; no live crawling. "
        "Only data/demo is reset."
    )
    for args in _build_demo_steps(config_path, demo_dir):
        stage_started = time.perf_counter()
        elapsed = stage_started - started
        remaining = 90.0 - elapsed
        if remaining <= 0:
            typer.echo("Demo exceeded its 90-second time budget.", err=True)
            raise typer.Exit(code=124)
        typer.echo(f"\n[demo] fbpipe {' '.join(args)}")
        try:
            subprocess.run(
                [sys.executable, "-m", "fbpipe.cli", *args],
                check=True,
                timeout=remaining,
            )
        except subprocess.TimeoutExpired as exc:
            typer.echo(
                "Demo exceeded its 90-second time budget while running "
                f"fbpipe {' '.join(args)}.",
                err=True,
            )
            raise typer.Exit(code=124) from exc
        except subprocess.CalledProcessError as exc:
            typer.echo(
                f"Demo stage failed: fbpipe {' '.join(args)} (exit={exc.returncode}).",
                err=True,
            )
            raise typer.Exit(code=exc.returncode or 1) from exc
        typer.echo(f"[demo] step elapsed: {time.perf_counter() - stage_started:.2f}s")

    try:
        _print_demo_top_terms(Path("data/demo/metrics/analyze.json"))
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=5) from exc

    total_seconds = time.perf_counter() - started
    typer.echo(f"\nDemo completed in {total_seconds:.2f}s (target: under 90s).")
    if total_seconds >= 90:
        typer.echo("Demo exceeded its 90-second time budget.", err=True)
        raise typer.Exit(code=124)


@app.command("validate")
def validate_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
) -> None:
    """Validate a Bronze JSONL file against RawPost."""
    from fbpipe.schema import RawPost

    valid = 0
    invalid = 0
    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                RawPost.model_validate_json(line)
                valid += 1
            except Exception as exc:  # validation errors are reported per line
                invalid += 1
                typer.echo(f"line {line_number}: {exc}", err=True)
    typer.echo(json.dumps({"valid": valid, "invalid": invalid}, ensure_ascii=False))
    if invalid:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
