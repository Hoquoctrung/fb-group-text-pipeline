"""Small offline tests for source-aware analysis and selected matplotlib figures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from fbpipe.analysis import analyze_corpus, load_silver, source_caption
from fbpipe.source import normalize_source


def _write_silver(path: Path, *, with_source: bool = True) -> None:
    records: list[dict[str, Any]] = [
        {
            "doc_id": "p1",
            "created_at": "2026-01-01T10:00:00Z",
            "n_tokens": 3,
            "tokens_nostop": ["piano", "nhac", "piano"],
            "text_clean": "piano nhac piano",
            "text_cased": "Piano nghe nhạc cùng Nguyễn Văn Minh",
            "source": "synthetic",
        },
        {
            "doc_id": "p2",
            "created_at": "2026-01-01T14:00:00Z",
            "n_tokens": 2,
            "tokens_nostop": ["hoc", "nhac"],
            "text_clean": "hoc nhac",
            "text_cased": "Học nhạc hôm nay",
            "source": "import",
        },
        {
            "doc_id": "p3",
            "created_at": "2026-01-02T09:00:00Z",
            "n_tokens": 4,
            "tokens_nostop": ["piano", "hoc", "band", "nhac"],
            "text_clean": "piano hoc band nhac",
            "text_cased": "Piano học cùng band",
            "source": "playwright_graphql",
        },
        {
            "doc_id": "p4",
            "created_at": None,
            "n_tokens": 1,
            "tokens_nostop": ["unknown"],
            "text_clean": "unknown",
            "text_cased": "Unknown token",
            "source": " ",
        },
    ]
    if not with_source:
        for record in records:
            record.pop("source", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(path, index=False)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_source_values_normalize_to_documented_categories() -> None:
    assert normalize_source("synthetic") == "synthetic"
    assert normalize_source("import") == "import"
    assert normalize_source("playwright_graphql") == "playwright"
    assert normalize_source("playwright_dom") == "playwright"
    assert normalize_source(" ") == "unknown"
    assert normalize_source(None) == "unknown"


def test_analysis_supports_legacy_silver_without_source(tmp_path: Path) -> None:
    silver = tmp_path / "silver.parquet"
    _write_silver(silver, with_source=False)

    loaded = load_silver(silver)
    result = analyze_corpus(input_path=silver, data_dir=tmp_path / "data")

    assert set(loaded["source"]) == {"unknown"}
    assert result["source_column_present"] is False
    assert result["source_counts"]["unknown"] == 4
    assert result["n_documents"] == 4
    assert Path(result["metrics_path"]).exists()


def test_analysis_normalizes_blank_and_playwright_source(tmp_path: Path) -> None:
    silver = tmp_path / "silver.parquet"
    _write_silver(silver)

    result = analyze_corpus(input_path=silver, data_dir=tmp_path / "data")
    loaded = load_silver(silver)

    assert result["source_counts"] == {
        "synthetic": 1,
        "import": 1,
        "playwright": 1,
        "unknown": 1,
    }
    assert "playwright=1" in source_caption(loaded)
    assert result["daily_posts"] == [
        {"date": "2026-01-01", "count": 2},
        {"date": "2026-01-02", "count": 1},
    ]


def test_viz_creates_only_requested_fast_figures(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    from fbpipe.viz import FIGURE_NAMES, generate_figures

    silver = tmp_path / "data" / "silver" / "documents.parquet"
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "docs" / "figures"
    _write_silver(silver)
    _write_json(
        data_dir / "metrics" / "represent.json",
        {
            "bow": {"dimensions": 3},
            "tfidf": {"dimensions": 3},
            "e5": {"available": True, "dimensions": 384},
        },
    )
    _write_json(
        data_dir / "metrics" / "label_eval.json",
        {
            "proxy_labels": True,
            "results": {
                "bow": {"macro_f1": 0.5},
                "tfidf": {"macro_f1": 0.6},
            },
        },
    )
    _write_json(
        data_dir / "metrics" / "bench_storage.json",
        {
            "n_documents": 1000,
            "cloned_from_silver": True,
            "sqlite": {
                "bulk_write": {"median_seconds": 0.04},
                "queries": {
                    "Q1_keyword_search": {"warm_median_seconds": 0.001},
                    "Q2_date_range": {"warm_median_seconds": 0.002},
                    "Q3_count_by_month": {"warm_median_seconds": 0.001},
                },
            },
            "parquet": {
                "bulk_write": {"median_seconds": 0.02},
                "queries": {
                    "Q1_keyword_scan": {"warm_median_seconds": 0.01},
                    "Q2_date_range_scan": {"warm_median_seconds": 0.004},
                    "Q3_count_by_month_scan": {"warm_median_seconds": 0.003},
                },
            },
        },
    )
    _write_json(
        data_dir / "metrics" / "preprocess.json",
        {
            "n_raw": 4,
            "n_after_dedup": 3,
            "n_after_spam": 3,
            "n_after_short": 2,
            "n_kept": 2,
        },
    )

    from scipy import sparse

    gold_dir = data_dir / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(
        gold_dir / "bow.npz",
        sparse.csr_matrix(
            [
                [3, 1, 0, 0, 0, 0],
                [0, 3, 1, 0, 0, 0],
                [0, 0, 3, 1, 0, 0],
                [0, 0, 0, 3, 1, 0],
            ],
            dtype=float,
        ),
    )
    sparse.save_npz(
        gold_dir / "tfidf.npz",
        sparse.csr_matrix(
            [
                [0.8, 0.2, 0, 0, 0, 0],
                [0, 0.8, 0.2, 0, 0, 0],
                [0, 0, 0.8, 0.2, 0, 0],
                [0, 0, 0, 0.8, 0.2, 0],
            ],
            dtype=float,
        ),
    )
    (gold_dir / "doc_ids.json").write_text(
        json.dumps(["p1", "p2", "p3", "p4"]), encoding="utf-8"
    )
    (gold_dir / "vocab.json").write_text(
        json.dumps({"bow": ["piano", "nhac", "hoc", "band", "tin", "nhac ly"]}),
        encoding="utf-8",
    )

    output_paths = generate_figures(
        input_path=silver,
        data_dir=data_dir,
        output_dir=output_dir,
    )

    assert [path.name for path in output_paths] == list(FIGURE_NAMES)
    assert "F09_lda_coherence.png" in {path.name for path in output_paths}
    assert "F11_embedding_map.png" in {path.name for path in output_paths}
    assert all(path.is_file() and path.stat().st_size > 0 for path in output_paths)
    assert (data_dir / "metrics" / "analyze.json").is_file()


def test_wordcloud_filter_removes_pii_and_multiword_name_heuristically() -> None:
    from fbpipe.viz import _wordcloud_frequencies

    frame = pd.DataFrame(
        [
            {
                "tokens_nostop": [
                    "piano",
                    "nguyen",
                    "van",
                    "minh",
                    "test",
                    "example",
                    "com",
                    "0912345678",
                    "nhac",
                ],
                "text_raw": "Liên hệ test@example.com hoặc 0912345678",
                "text_clean": "piano nguyen van minh test example com 0912345678 nhac",
                "text_cased": "Piano cùng Nguyễn Văn Minh",
            }
        ]
    )

    frequencies = _wordcloud_frequencies(frame)

    assert frequencies["piano"] == 1
    assert frequencies["nhac"] == 1
    assert not {"nguyen", "van", "minh", "test", "example", "com"} & frequencies.keys()
    assert "0912345678" not in frequencies


def test_lda_curve_falls_back_to_sklearn_perplexity_without_gensim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    from scipy import sparse

    from fbpipe.viz import _lda_curve

    real_import = builtins.__import__

    def import_without_gensim(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "gensim" or name.startswith("gensim."):
            raise ImportError("gensim intentionally unavailable for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_gensim)

    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    sparse.save_npz(
        gold_dir / "bow.npz",
        sparse.csr_matrix(
            [
                [3, 1, 0, 0, 0, 0],
                [0, 3, 1, 0, 0, 0],
                [0, 0, 3, 1, 0, 0],
                [0, 0, 0, 3, 1, 0],
            ],
            dtype=float,
        ),
    )
    (gold_dir / "vocab.json").write_text(
        json.dumps({"bow": ["piano", "nhac", "hoc", "band", "tin", "ly"]}),
        encoding="utf-8",
    )
    frame = pd.DataFrame(
        {
            "tokens_nostop": [
                ["piano", "nhac"],
                ["nhac", "hoc"],
                ["hoc", "band"],
                ["band", "tin", "ly"],
            ]
        }
    )

    ks, scores, metric, best_k = _lda_curve(frame, tmp_path)

    assert ks == list(range(3, 11))
    assert len(scores) == len(ks)
    assert all(pd.notna(score) for score in scores)
    assert metric == "perplexity"
    assert best_k in ks


def test_embedding_map_falls_back_to_tfidf_svd_without_e5(tmp_path: Path) -> None:
    from scipy import sparse

    from fbpipe.viz import _embedding_map_data

    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    sparse.save_npz(
        gold_dir / "tfidf.npz",
        sparse.csr_matrix(
            [
                [0.8, 0.2, 0, 0, 0, 0],
                [0, 0.8, 0.2, 0, 0, 0],
                [0, 0, 0.8, 0.2, 0, 0],
                [0, 0, 0, 0.8, 0.2, 0],
            ],
            dtype=float,
        ),
    )
    doc_ids = ["p1", "p2", "p3", "p4"]
    (gold_dir / "doc_ids.json").write_text(json.dumps(doc_ids), encoding="utf-8")
    frame = pd.DataFrame({"doc_id": doc_ids})

    coordinates, clusters, title, method = _embedding_map_data(frame, tmp_path)

    assert coordinates.shape == (4, 2)
    assert len(clusters) == 4
    assert method == "TruncatedSVD 2D từ TF-IDF"
    assert "KMeans" in title
    assert "fallback" in title


def test_f09_f11_render_200dpi_without_tight_layout_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import warnings

    pytest.importorskip("matplotlib")
    from PIL import Image
    from scipy import sparse

    import fbpipe.viz as viz

    frame = pd.DataFrame(
        {
            "doc_id": ["p1", "p2", "p3", "p4"],
            "tokens_nostop": [
                ["piano", "nhac"],
                ["nhac", "hoc"],
                ["hoc", "band"],
                ["band", "tin", "ly"],
            ],
        }
    )
    gold_dir = tmp_path / "data" / "gold"
    gold_dir.mkdir(parents=True)
    sparse.save_npz(
        gold_dir / "tfidf.npz",
        sparse.csr_matrix(
            [
                [0.8, 0.2, 0, 0, 0, 0],
                [0, 0.8, 0.2, 0, 0, 0],
                [0, 0, 0.8, 0.2, 0, 0],
                [0, 0, 0, 0.8, 0.2, 0],
            ],
            dtype=float,
        ),
    )
    (gold_dir / "doc_ids.json").write_text(
        json.dumps(frame["doc_id"].tolist()), encoding="utf-8"
    )
    monkeypatch.setattr(
        viz,
        "_lda_curve",
        lambda *_args: (
            list(range(3, 11)),
            [float(value) for value in range(10, 2, -1)],
            "perplexity",
            10,
        ),
    )
    output_dir = tmp_path / "docs" / "figures"
    output_dir.mkdir(parents=True)
    plt = viz._pyplot()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        viz._draw_f09(plt, frame, tmp_path / "data", output_dir, "Nguồn: synthetic=4")
        viz._draw_f11(plt, frame, tmp_path / "data", output_dir, "Nguồn: synthetic=4")

    for filename in ("F09_lda_coherence.png", "F11_embedding_map.png"):
        path = output_dir / filename
        assert path.is_file() and path.stat().st_size > 0
        with Image.open(path) as image:
            assert image.info["dpi"][0] == pytest.approx(200, abs=1)
    assert not any("tight_layout" in str(item.message) for item in captured)
