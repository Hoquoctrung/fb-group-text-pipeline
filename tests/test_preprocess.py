"""Table-driven input/output tests for all S0-S11 transforms."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from fbpipe.collect.synthetic import SyntheticCollector
from fbpipe.preprocess.pipeline import preprocess_corpus
from fbpipe.preprocess.steps import build_transforms

RESOURCES = Path("resources")


def _transform_by_name(name: str, resource_dir: Path = RESOURCES):
    transforms, _ = build_transforms(
        resource_dir,
        english_words=None,
        load_english_reference=False,
    )
    return next(
        transform for transform in transforms if transform.name.startswith(name)
    )


STEP_CASES: list[tuple[str, dict[str, Any], str, Any]] = [
    (
        "S0",
        {"text_raw": "Mình thích nhạc piano"},
        "lang",
        "vi",
    ),
    (
        "S1",
        {
            "text_raw": "e\u0302\u0301  “ok”\u200b",
            "text_clean": "e\u0302\u0301  “ok”\u200b",
        },
        "text_clean",
        'ế "ok"',
    ),
    (
        "S2",
        {"text_clean": "Bài hay Xem thêm"},
        "text_clean",
        "Bài hay",
    ),
    (
        "S3",
        {
            "text_clean": (
                "Hi @trung foo@example.com https://example.com 0901234567 #Piano"
            )
        },
        "n_url",
        1,
    ),
    (
        "S4",
        {"text_clean": "Piano 😊"},
        "n_emoji",
        1,
    ),
    (
        "S5",
        {"text_clean": "đẹpppp quá!!!!!"},
        "text_clean",
        "đẹpp quá!",
    ),
    (
        "S6",
        {"text_clean": "ko dc k biết 5k mk ad r"},
        "text_clean",
        "không được không biết 5k mk ad rồi",
    ),
    (
        "S7",
        {"text_clean": "HELLO Piano"},
        "text_cased",
        "HELLO Piano",
    ),
    (
        "S8",
        {"text_clean": "hello piano"},
        "tokens",
        ["hello", "piano"],
    ),
    (
        "S9",
        {"tokens": ["the", "piano", "và", "âm_nhạc"]},
        "tokens_nostop",
        ["piano", "âm_nhạc"],
    ),
    (
        "S10",
        {"tokens_nostop": ["running", "học_viên"]},
        "stems",
        ["running", "học_viên"],
    ),
    (
        "S11",
        {
            "text_raw": "INBOX giá rẻ sale 0901234567 https://example.com",
            "text_clean": "inbox giá rẻ sale <phone> <url>",
            "tokens": ["inbox", "giá", "rẻ", "sale", "thông_tin"],
            "n_tokens": 5,
            "n_url": 1,
            "n_repeated_runs": 0,
        },
        "is_spam",
        True,
    ),
]


@pytest.mark.parametrize(
    ("step_name", "input_doc", "expected_key", "expected_value"),
    STEP_CASES,
    ids=[f"{case[0]}_{case[2]}" for case in STEP_CASES],
)
def test_transform_input_output_table(
    step_name: str,
    input_doc: dict[str, Any],
    expected_key: str,
    expected_value: Any,
) -> None:
    # Use the repository resources for transformations that consume dictionaries.
    original_doc = copy.deepcopy(input_doc)
    transform = _transform_by_name(step_name)
    result = transform.apply(input_doc)
    assert result[expected_key] == expected_value
    assert input_doc == original_doc


def test_s3_replaces_pii_and_keeps_hashtag_text() -> None:
    result = _transform_by_name("S3").apply(
        {
            "text_clean": (
                "Hi @trung foo@example.com https://example.com 0901234567 #Piano"
            )
        }
    )
    assert "<URL>" in result["text_clean"]
    assert "<EMAIL>" in result["text_clean"]
    assert "<PHONE>" in result["text_clean"]
    assert "<USER>" in result["text_clean"]
    assert "Piano" in result["text_clean"]
    assert result["hashtags"] == ["Piano"]
    assert result["n_hashtag"] == 1


def test_s6_does_not_expand_ambiguous_mk_ad_or_number_suffix_k() -> None:
    result = _transform_by_name("S6").apply({"text_clean": "5k mk ad k biết"})
    assert result["text_clean"] == "5k mk ad không biết"


def test_ablation_has_exactly_three_configurations() -> None:
    from fbpipe.preprocess.pipeline import _ablation_metrics

    transforms, _ = build_transforms(
        RESOURCES,
        load_english_reference=False,
    )
    raw_docs = [
        {"doc_id": "one", "text_raw": "Mình thích piano"},
        {"doc_id": "two", "text_raw": "I like music"},
    ]
    processed = []
    for record in raw_docs:
        current = dict(record)
        current["text_clean"] = record["text_raw"]
        for transform in transforms:
            current = transform.apply(current)
        processed.append(current)
    results = _ablation_metrics(raw_docs, processed, transforms)
    assert [item["name"] for item in results] == [
        "A0_strip_only",
        "A1_clean_and_tokenize",
        "A2_full_s0_s11",
    ]


def test_preprocess_writes_parquet_and_metrics(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    import pandas as pd

    data_dir = tmp_path / "data"
    bronze_dir = data_dir / "bronze"
    resources_dir = tmp_path / "resources"
    bronze_dir.mkdir(parents=True)
    resources_dir.mkdir()
    shutil.copy(RESOURCES / "vi_stopwords.txt", resources_dir / "vi_stopwords.txt")
    shutil.copy(RESOURCES / "vi_teencode.tsv", resources_dir / "vi_teencode.tsv")
    shutil.copy(RESOURCES / "vi_ambiguous.txt", resources_dir / "vi_ambiguous.txt")
    shutil.copy(
        RESOURCES / "en_extra_stopwords.txt",
        resources_dir / "en_extra_stopwords.txt",
    )
    (resources_dir / "domain_stopwords.txt").write_text(
        "# approved domain stopwords\n", encoding="utf-8"
    )
    bronze_path = bronze_dir / "sample.jsonl"
    posts = list(SyntheticCollector(n=4, seed=42).iter_posts())
    bronze_path.write_text(
        "".join(post.model_dump_json() + "\n" for post in posts),
        encoding="utf-8",
    )

    result = preprocess_corpus(
        input_dir=bronze_dir,
        output_path=data_dir / "silver" / "documents.parquet",
        data_dir=data_dir,
        resource_dir=resources_dir,
        force=True,
    )
    assert result.output_path.exists()
    assert result.metrics_path.exists()
    frame = pd.read_parquet(result.output_path)
    assert len(frame) == 4
    assert {"text_clean", "tokens", "tokens_nostop", "keep", "source"}.issubset(
        frame.columns
    )
    assert set(frame["source"]) == {"synthetic"}
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert len(metrics["ablation"]) == 3
    assert metrics["n_raw"] == 4


def test_preprocess_refuses_missing_bronze_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No Bronze .jsonl files"):
        preprocess_corpus(
            input_dir=tmp_path / "empty-bronze",
            output_path=tmp_path / "silver" / "documents.parquet",
            data_dir=tmp_path / "data",
            resource_dir=tmp_path / "resources",
        )
