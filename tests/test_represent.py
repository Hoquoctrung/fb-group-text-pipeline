"""Tests for deterministic sparse representations and optional E5 handling."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from fbpipe.represent.pipeline import (
    _e5_embeddings,
    build_classical_representations,
    represent_corpus,
)


def _documents() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "doc_id": [f"doc-{index}" for index in range(6)],
            "tokens_nostop": [
                ["piano", "music", "lesson"],
                ["piano", "music", "practice"],
                ["piano", "keyboard", "lesson"],
                ["recruitment", "job", "developer"],
                ["recruitment", "job", "engineer"],
                ["recruitment", "career", "developer"],
            ],
            "text_clean": [
                "Piano music lesson",
                "Piano music practice",
                "Piano keyboard lesson",
                "Recruitment job developer",
                "Recruitment job engineer",
                "Recruitment career developer",
            ],
        }
    )


def test_bow_and_tfidf_are_sparse_and_aligned() -> None:
    result = build_classical_representations(
        _documents(),
        {
            "bow": {"min_df": 1, "max_df": 1.0, "ngram": [1, 2]},
            "tfidf": {"min_df": 1, "max_df": 1.0, "ngram": [1, 2]},
        },
    )
    assert result["bow"].shape[0] == 6
    assert result["tfidf"].shape[0] == 6
    assert result["bow"].shape[1] == len(result["bow_terms"])
    assert result["tfidf"].shape[1] == len(result["tfidf_terms"])
    assert result["bow"].nnz > 0
    assert result["tfidf"].nnz > 0
    assert result["top_tf"]
    assert result["top_tfidf"]


def test_tiny_corpus_falls_back_to_permissive_thresholds() -> None:
    frame = _documents().iloc[:2].copy()
    result = build_classical_representations(
        frame,
        {"bow": {"min_df": 3, "max_df": 0.8, "ngram": [1, 2]}},
    )
    assert result["bow"].shape[0] == 2
    assert result["bow_fallback_thresholds"] is True


def test_missing_sentence_transformers_skips_e5_with_warning(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    with pytest.warns(RuntimeWarning, match="sentence-transformers is unavailable"):
        result, metrics = _e5_embeddings(
            ["query: test"],
            cache_path=tmp_path / "e5.npy",
            cache_meta_path=tmp_path / "e5.json",
            cache_key="key",
            model_name="intfloat/multilingual-e5-small",
            prefix="query: ",
            batch_size=2,
            force=True,
        )
    assert result is None
    assert metrics["available"] is False
    assert "pip install -e '.[embed]'" in metrics["warning"]


def test_e5_cache_loads_without_importing_optional_library(
    tmp_path, monkeypatch
) -> None:
    cache_path = tmp_path / "e5.npy"
    meta_path = tmp_path / "e5.json"
    expected = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    np.save(cache_path, expected, allow_pickle=False)
    meta_path.write_text(
        '{"cache_key":"same","model":"model","rows":2}', encoding="utf-8"
    )
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    result, metrics = _e5_embeddings(
        ["a", "b"],
        cache_path=cache_path,
        cache_meta_path=meta_path,
        cache_key="same",
        model_name="model",
        prefix="query: ",
        batch_size=2,
        force=False,
    )
    assert np.array_equal(result, expected)
    assert metrics["cached"] is True


def test_e5_model_load_error_warns_and_does_not_keep_stale_cache(
    tmp_path, monkeypatch
) -> None:
    import types

    fake_module = types.ModuleType("sentence_transformers")

    class BrokenModel:  # noqa: D101
        def __init__(self, model_name: str) -> None:
            raise OSError("model download failed")

    fake_module.SentenceTransformer = BrokenModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    cache_path = tmp_path / "e5.npy"
    meta_path = tmp_path / "e5.json"
    np.save(cache_path, np.ones((1, 2), dtype=np.float32), allow_pickle=False)
    meta_path.write_text('{"cache_key":"old"}', encoding="utf-8")

    with pytest.warns(RuntimeWarning, match="model could not load or encode"):
        result, metrics = _e5_embeddings(
            ["current text"],
            cache_path=cache_path,
            cache_meta_path=meta_path,
            cache_key="new-key",
            model_name="intfloat/multilingual-e5-small",
            prefix="query: ",
            batch_size=2,
            force=False,
        )

    assert result is None
    assert metrics["available"] is False
    assert not cache_path.exists()
    assert not meta_path.exists()


def test_represent_corpus_writes_artifacts_and_skips_unchanged_input(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "documents.parquet"
    source.write_bytes(b"stable fixture bytes")
    frame = _documents()
    monkeypatch.setattr(
        "fbpipe.represent.pipeline.pd.read_parquet", lambda _: frame.copy()
    )
    output = tmp_path / "gold"
    data_dir = tmp_path / "data"
    settings = {
        "bow": {"min_df": 1, "max_df": 1.0, "ngram": [1, 2]},
        "tfidf": {"min_df": 1, "max_df": 1.0, "ngram": [1, 2]},
    }

    first = represent_corpus(
        input_path=source,
        output_dir=output,
        data_dir=data_dir,
        settings=settings,
        include_e5=False,
    )
    assert first["n_documents"] == len(frame)
    assert (output / "bow.npz").exists()
    assert (output / "tfidf.npz").exists()
    assert (output / "vocab.json").exists()
    assert (output / "doc_ids.json").exists()
    assert (data_dir / "metrics" / "represent.json").exists()

    second = represent_corpus(
        input_path=source,
        output_dir=output,
        data_dir=data_dir,
        settings=settings,
        include_e5=False,
    )
    assert second["skipped_as_up_to_date"] is True
