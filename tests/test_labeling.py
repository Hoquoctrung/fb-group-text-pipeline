"""Tests for stratified label samples, proxy labels, and macro-F1 evaluation."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import sparse

from fbpipe.represent.labeling import (
    _macro_f1_for_matrix,
    build_proxy_labels,
    stratified_sample,
    weak_label,
)


def _frame() -> pd.DataFrame:
    texts = [
        "Cho hỏi piano học ở đâu?",
        "Ai biết lớp piano không?",
        "Làm sao học hợp âm?",
        "Cho hỏi lịch học piano?",
        "Thông báo lịch học vào ngày mai",
        "Kính mời tham dự chương trình",
        "Thông báo đổi lịch học",
        "Trân trọng thông báo sự kiện",
        "Tuyển dụng developer",
        "Tuyển gấp kỹ sư",
        "Việc làm và ứng tuyển",
        "Cơ hội việc làm",
    ]
    return pd.DataFrame(
        {
            "doc_id": [f"id-{index}" for index in range(len(texts))],
            "year_month": [
                "2026-01" if index < 6 else "2026-02" for index in range(len(texts))
            ],
            "text_clean": texts,
            "tokens_nostop": [text.split() for text in texts],
        }
    )


def test_stratified_sample_has_expected_columns_and_is_deterministic() -> None:
    frame = _frame()
    sample_a = stratified_sample(frame, n=8, seed=42)
    sample_b = stratified_sample(frame, n=8, seed=42)
    assert list(sample_a.columns) == ["doc_id", "text_clean_preview", "label"]
    assert len(sample_a) == 8
    assert sample_a["doc_id"].tolist() == sample_b["doc_id"].tolist()
    assert set(sample_a["label"]) == {""}


def test_weak_label_rules_are_explicit_and_proxy_flag_is_set() -> None:
    assert weak_label("Cho hỏi lớp piano ở đâu?") == "hoi_dap"
    assert weak_label("Tuyển dụng developer") == "tim_kiem_tuyen_dung"
    proxy = build_proxy_labels(_frame())
    assert proxy["proxy_labels"].all()
    assert set(proxy["label"]).issubset(
        {
            "hoi_dap",
            "chia_se",
            "thong_bao",
            "tim_kiem_tuyen_dung",
            "quang_cao_spam",
            "khac",
        }
    )


def test_macro_f1_returns_score_with_balanced_classes() -> None:
    labels = ["question"] * 6 + ["notice"] * 6
    features = sparse.csr_matrix(
        np.array([[1, 0] if label == "question" else [0, 1] for label in labels])
    )
    result = _macro_f1_for_matrix(features, labels, seed=42)
    assert result["macro_f1"] == 1.0
    assert result["cv_folds"] == 5


def test_macro_f1_explains_insufficient_labels() -> None:
    result = _macro_f1_for_matrix(
        sparse.csr_matrix(np.eye(3)), ["only", "only", "single"]
    )
    assert result["macro_f1"] is None
    assert "two classes" in result["reason"]


def test_label_eval_uses_and_marks_proxy_labels_when_human_labels_absent(
    tmp_path, monkeypatch
) -> None:
    from fbpipe.represent.labeling import evaluate_labels

    texts = (
        ["Cho hỏi nơi học piano?" for _ in range(4)]
        + ["Thông báo lịch học mới" for _ in range(4)]
        + ["Tuyển dụng developer" for _ in range(4)]
    )
    frame = pd.DataFrame(
        {
            "doc_id": [f"doc-{index}" for index in range(12)],
            "text_clean": texts,
            "text_raw": texts,
            "tokens_nostop": [text.split() for text in texts],
        }
    )
    source = tmp_path / "documents.parquet"
    source.touch()
    manual_labels = tmp_path / "to_label.csv"
    manual_labels.write_text("doc_id,text_clean_preview,label\n", encoding="utf-8")
    representation_dir = tmp_path / "gold"
    representation_dir.mkdir()
    (representation_dir / "doc_ids.json").write_text(
        json.dumps(frame["doc_id"].tolist()), encoding="utf-8"
    )
    features = np.vstack([[1, 0, 0]] * 4 + [[0, 1, 0]] * 4 + [[0, 0, 1]] * 4)
    sparse.save_npz(representation_dir / "bow.npz", sparse.csr_matrix(features))
    sparse.save_npz(representation_dir / "tfidf.npz", sparse.csr_matrix(features))
    monkeypatch.setattr(
        "fbpipe.represent.labeling.pd.read_parquet", lambda _: frame.copy()
    )

    import pytest

    with pytest.warns(RuntimeWarning, match="proxy labels"):
        result = evaluate_labels(
            input_path=source,
            labels_path=manual_labels,
            represent_dir=representation_dir,
            data_dir=tmp_path / "data",
            seed=42,
        )
    assert result["proxy_labels"] is True
    assert result["results"]["bow"]["proxy_labels"] is True
    assert result["n_labeled"] == 12
    assert (tmp_path / "data" / "labels" / "proxy_labels.csv").exists()
    assert (tmp_path / "data" / "metrics" / "label_eval.json").exists()
