"""Bronze JSONL to Silver Parquet preprocessing pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fbpipe.metrics import write_metrics
from fbpipe.preprocess.steps import (
    Transform,
    build_transforms,
    load_english_reference_words,
    tokenize_for_ablation,
)
from fbpipe.privacy import scrub_pii
from fbpipe.schema import RawPost
from fbpipe.source import normalize_source

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "doc_id",
    "parent_id",
    "doc_type",
    "source",
    "created_at",
    "year_month",
    "author_hash",
    "lang",
    "text_raw",
    "text_clean",
    "text_cased",
    "text_demojized",
    "hashtags",
    "tokens",
    "tokens_nostop",
    "stems",
    "lemmas",
    "n_tokens",
    "n_emoji",
    "n_url",
    "n_hashtag",
    "has_diacritics_ratio",
    "teencode_hits",
    "is_duplicate",
    "dup_group",
    "is_spam",
    "spam_score",
    "is_short",
    "keep",
    "reactions_total",
    "comments_count",
    "is_code_mixed",
    "oov_tokens",
]


@dataclass(frozen=True)
class PreprocessResult:
    """Summary returned by one preprocessing run."""

    input_files: int
    raw_records: int
    output_records: int
    invalid_records: int
    output_path: Path
    metrics_path: Path
    skipped_as_up_to_date: bool = False


def _token_quality_metrics(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure one-character tokens and flag suspiciously high ratios."""
    tokens = [
        str(token)
        for doc in docs
        for token in (doc.get("tokens") or [])
        if str(token)
    ]
    total_tokens = len(tokens)
    single_character_tokens = sum(len(token) == 1 for token in tokens)
    ratio = (
        round(single_character_tokens / total_tokens, 6) if total_tokens else 0.0
    )
    quality_warnings: list[str] = []
    threshold = 0.10
    if ratio > threshold:
        message = (
            f"Single-character token ratio is {ratio:.1%}, above the 10% threshold. "
            "Review Unicode-aware tokenization."
        )
        quality_warnings.append(message)
        logger.warning("Text quality warning: %s", message)
    return {
        "total_tokens": total_tokens,
        "single_character_tokens": single_character_tokens,
        "single_character_token_ratio": ratio,
        "warning_threshold_ratio": threshold,
        "warnings": quality_warnings,
    }


def _read_bronze(input_files: list[Path]) -> tuple[list[dict[str, Any]], int, int]:
    records: list[dict[str, Any]] = []
    invalid_records = 0
    raw_records = 0
    seen_post_ids: set[str] = set()
    for path in input_files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw_records += 1
                try:
                    post = RawPost.model_validate_json(line)
                except Exception:  # malformed Bronze lines are counted, not hidden
                    invalid_records += 1
                    continue
                if post.post_id in seen_post_ids:
                    continue
                seen_post_ids.add(post.post_id)
                created_at = post.created_at
                year_month = created_at.strftime("%Y-%m") if created_at else None
                records.append(
                    {
                        "doc_id": post.post_id,
                        "parent_id": None,
                        "doc_type": "post",
                        "source": normalize_source(post.source),
                        "created_at": created_at,
                        "year_month": year_month,
                        "author_hash": post.author_hash,
                        "text_raw": post.text,
                        "reactions_total": post.reactions_total,
                        "comments_count": post.comments_count,
                        "source_file": str(path),
                    }
                )
    return records, raw_records, invalid_records


def _prepare_doc(
    record: dict[str, Any],
    transforms: list[Transform],
    step_seconds: dict[str, float] | None = None,
    english_words: set[str] | None = None,
) -> dict[str, Any]:
    doc = dict(record)
    doc["text_clean"] = str(record.get("text_raw") or "")
    for transform in transforms:
        started = time.perf_counter()
        doc = transform.apply(doc)
        elapsed = time.perf_counter() - started
        if step_seconds is not None:
            step_seconds[transform.name] = (
                step_seconds.get(transform.name, 0.0) + elapsed
            )
    tokens = doc.get("tokens", [])
    doc["is_code_mixed"] = _is_code_mixed(doc, tokens)
    if english_words is not None:
        doc["oov_tokens"] = [
            token
            for token in tokens
            if token.isascii()
            and token.isalpha()
            and len(token) >= 3
            and token.casefold() not in english_words
        ]
    else:
        doc["oov_tokens"] = []
    return doc


def _is_code_mixed(doc: dict[str, Any], tokens: list[str]) -> bool:
    has_vi_diacritics = float(doc.get("has_diacritics_ratio", 0.0)) > 0.0
    english_tokens = [
        token
        for token in tokens
        if token.isascii() and token.isalpha() and len(token) >= 3
    ]
    return has_vi_diacritics and bool(english_tokens)


def _shingles(tokens: list[str], size: int) -> set[str]:
    if not tokens:
        return set()
    if len(tokens) < size:
        return {" ".join(tokens)}
    return {
        " ".join(tokens[index : index + size])
        for index in range(len(tokens) - size + 1)
    }


def _mark_duplicates(
    docs: list[dict[str, Any]],
    *,
    threshold: float = 0.85,
    shingle_size: int = 3,
) -> tuple[str, int]:
    """Mark exact and MinHash near-duplicates; exact hash is a safe fallback."""
    duplicate_count = 0
    try:
        from datasketch import MinHash, MinHashLSH
    except ImportError:
        seen_hashes: dict[str, int] = {}
        for index, doc in enumerate(docs):
            signature_tokens = doc.get("tokens_nostop", []) or doc.get("tokens", [])
            signature_text = " ".join(signature_tokens)
            signature = hashlib.sha1(signature_text.encode("utf-8")).hexdigest()
            if signature in seen_hashes:
                representative = seen_hashes[signature]
                doc["is_duplicate"] = True
                doc["dup_group"] = docs[representative]["dup_group"] or (
                    f"dup-{docs[representative]['doc_id']}"
                )
                docs[representative]["dup_group"] = doc["dup_group"]
                doc["keep"] = False
                duplicate_count += 1
            else:
                seen_hashes[signature] = index
        return "exact_hash_fallback", duplicate_count

    lsh = MinHashLSH(threshold=threshold, num_perm=64)
    for index, doc in enumerate(docs):
        key = f"row-{index}"
        shingles = _shingles(doc.get("tokens_nostop", []), shingle_size)
        if not shingles:
            shingles = {f"empty-doc-{doc['doc_id']}"}
        signature = MinHash(num_perm=64)
        for shingle in sorted(shingles):
            signature.update(shingle.encode("utf-8"))
        matches = sorted(lsh.query(signature))
        if matches:
            matched_index = int(matches[0].split("-", maxsplit=1)[1])
            representative_doc = docs[matched_index]
            group = representative_doc["dup_group"] or (
                f"dup-{representative_doc['doc_id']}"
            )
            representative_doc["dup_group"] = group
            doc["is_duplicate"] = True
            doc["dup_group"] = group
            doc["keep"] = False
            duplicate_count += 1
        else:
            lsh.insert(key, signature)
    return "datasketch_minhash_lsh", duplicate_count


def _ablation_metrics(
    raw_records: list[dict[str, Any]],
    processed_records: list[dict[str, Any]],
    transforms: list[Transform],
) -> list[dict[str, Any]]:
    configurations: list[dict[str, Any]] = []

    def summarize(name: str, token_lists: list[list[str]], description: str) -> None:
        vocabulary = {token for tokens in token_lists for token in tokens}
        lengths = [len(tokens) for tokens in token_lists]
        configurations.append(
            {
                "name": name,
                "description": description,
                "documents": len(token_lists),
                "vocabulary_size": len(vocabulary),
                "average_tokens": round(sum(lengths) / len(lengths), 4)
                if lengths
                else 0.0,
            }
        )

    a0_tokens = [
        tokenize_for_ablation(str(record.get("text_raw") or "").strip())
        for record in raw_records
    ]
    summarize(
        "A0_strip_only",
        a0_tokens,
        "Whitespace strip only; regex tokens used for measurement.",
    )

    a1_tokens: list[list[str]] = []
    for record in raw_records:
        current = dict(record)
        current["text_clean"] = str(record.get("text_raw") or "")
        for transform in transforms[:9]:
            current = transform.apply(current)
        a1_tokens.append(current.get("tokens", []))
    summarize(
        "A1_clean_and_tokenize",
        a1_tokens,
        "S0-S8: language, normalization, cleanup, teencode, lowercase, tokenization.",
    )

    a2_tokens = [list(record.get("tokens_nostop", [])) for record in processed_records]
    summarize(
        "A2_full_s0_s11",
        a2_tokens,
        "Full S0-S11 result; vocabulary measured after stopword removal.",
    )
    return configurations


def _domain_stopword_candidates(
    docs: list[dict[str, Any]], resource_file: Path
) -> list[str]:
    document_frequency: Counter[str] = Counter()
    for doc in docs:
        document_frequency.update(set(doc.get("tokens", [])))
    count = len(docs)
    if count == 0:
        return []
    active_stopwords: set[str] = set()
    for filename in (
        "vi_stopwords.txt",
        "en_extra_stopwords.txt",
        "domain_stopwords.txt",
    ):
        candidate_path = resource_file.parent / filename
        try:
            active_stopwords.update(
                line.strip().casefold()
                for line in candidate_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )
        except OSError:
            continue
    return sorted(
        token
        for token, frequency in document_frequency.items()
        if frequency / count > 0.5
        and len(token) > 1
        and not token.startswith("<")
        and token not in active_stopwords
    )


def _append_domain_stopword_suggestions(path: Path, candidates: list[str]) -> None:
    if not candidates:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    already_suggested = {
        line.split(":", maxsplit=1)[1].strip().casefold()
        for line in existing.splitlines()
        if line.lstrip().startswith("# candidate:") and ":" in line
    }
    new_candidates = [
        item for item in candidates if item.casefold() not in already_suggested
    ]
    if new_candidates:
        with path.open("a", encoding="utf-8") as handle:
            for token in new_candidates:
                handle.write(f"# candidate: {token}\n")


def _is_up_to_date(
    output_path: Path,
    metrics_path: Path,
    input_files: list[Path],
    resource_files: list[Path],
) -> bool:
    if not output_path.exists() or not metrics_path.exists() or not input_files:
        return False
    latest_input = max(
        path.stat().st_mtime
        for path in [*input_files, *resource_files]
        if path.exists()
    )
    return (
        output_path.stat().st_mtime >= latest_input
        and metrics_path.stat().st_mtime >= latest_input
    )


def preprocess_corpus(
    *,
    input_dir: str | Path = "data/bronze",
    output_path: str | Path = "data/silver/documents.parquet",
    data_dir: str | Path = "data",
    resource_dir: str | Path = "resources",
    settings: dict[str, Any] | None = None,
    force: bool = False,
) -> PreprocessResult:
    """Preprocess all Bronze JSONL files into Silver Parquet and metrics."""
    input_root = Path(input_dir)
    output = Path(output_path)
    metrics_path = Path(data_dir) / "metrics" / "preprocess.json"
    resources = Path(resource_dir)
    input_files = sorted(input_root.glob("*.jsonl")) if input_root.exists() else []
    if not input_files:
        raise FileNotFoundError(f"No Bronze .jsonl files found in {input_root}")
    resource_files = sorted(resources.glob("*")) if resources.exists() else []
    options = settings or {}
    settings_fingerprint = hashlib.sha256(
        json.dumps(options, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()
    if not force and _is_up_to_date(output, metrics_path, input_files, resource_files):
        try:
            old_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            if old_metrics.get("settings_fingerprint") == settings_fingerprint:
                record_count = int(old_metrics.get("n_documents", 0))
                return PreprocessResult(
                    input_files=len(input_files),
                    raw_records=record_count,
                    output_records=record_count,
                    invalid_records=0,
                    output_path=output,
                    metrics_path=metrics_path,
                    skipped_as_up_to_date=True,
                )
        except (OSError, ValueError, TypeError):
            pass

    started = time.perf_counter()
    raw_docs, raw_line_count, invalid_records = _read_bronze(input_files)
    english_words = load_english_reference_words()
    transforms, resource_metadata = build_transforms(
        resources,
        collapse_repeats_to=int(options.get("collapse_repeats_to", 2)),
        min_tokens=int(options.get("min_tokens", 3)),
        english_words=english_words,
        load_english_reference=False,
    )
    step_seconds: dict[str, float] = {}
    docs = [
        _prepare_doc(record, transforms, step_seconds, english_words)
        for record in raw_docs
    ]

    dedup_method, duplicate_count = _mark_duplicates(
        docs,
        threshold=float(options.get("dedup", {}).get("threshold", 0.85)),
        shingle_size=int(options.get("dedup", {}).get("shingle", 3)),
    )
    for doc in docs:
        doc["keep"] = not (
            bool(doc.get("is_duplicate"))
            or bool(doc.get("is_short"))
            or bool(doc.get("is_spam"))
        )

    n_raw = len(docs)
    n_after_dedup = sum(not doc["is_duplicate"] for doc in docs)
    n_after_spam = sum(not doc["is_duplicate"] and not doc["is_spam"] for doc in docs)
    n_after_short = sum(
        not doc["is_duplicate"] and not doc["is_spam"] and not doc["is_short"]
        for doc in docs
    )
    n_kept = sum(bool(doc["keep"]) for doc in docs)

    vocabulary_available = resource_metadata["english_reference_vocabulary_available"]
    oov_counter: Counter[str] = Counter()
    if vocabulary_available:
        for doc in docs:
            oov_counter.update(token.casefold() for token in doc["oov_tokens"])
        total_english_tokens = sum(
            1
            for doc in docs
            for token in doc["tokens"]
            if token.isascii() and token.isalpha() and len(token) >= 3
        )
        oov_total = sum(oov_counter.values())
        oov_ratio: float | None = (
            round(oov_total / total_english_tokens, 6) if total_english_tokens else 0.0
        )
    else:
        oov_ratio = None

    all_token_counts = [int(doc.get("n_tokens", 0)) for doc in docs]
    lengths_sorted = sorted(all_token_counts)
    length_distribution = {
        "min": min(lengths_sorted) if lengths_sorted else 0,
        "median": lengths_sorted[len(lengths_sorted) // 2] if lengths_sorted else 0,
        "mean": round(sum(lengths_sorted) / len(lengths_sorted), 4)
        if lengths_sorted
        else 0.0,
        "max": max(lengths_sorted) if lengths_sorted else 0,
    }
    doc_count = len(docs)
    no_diacritics_count = sum(
        float(doc.get("has_diacritics_ratio", 0.0)) == 0.0 for doc in docs
    )
    teencode_docs = sum(int(doc.get("teencode_hits", 0)) > 0 for doc in docs)
    code_mixed_docs = sum(bool(doc.get("is_code_mixed")) for doc in docs)
    domain_stopword_path = resources / "domain_stopwords.txt"
    domain_candidates = _domain_stopword_candidates(docs, domain_stopword_path)
    _append_domain_stopword_suggestions(domain_stopword_path, domain_candidates)
    ablation_started = time.perf_counter()
    ablation = _ablation_metrics(raw_docs, docs, transforms)
    ablation_seconds = time.perf_counter() - ablation_started
    pipeline_seconds = time.perf_counter() - started

    metrics: dict[str, Any] = {
        "input_files": [str(path) for path in input_files],
        "settings_fingerprint": settings_fingerprint,
        "n_raw": n_raw,
        "n_documents": len(docs),
        "n_raw_lines": raw_line_count,
        "n_invalid_records": invalid_records,
        "n_duplicate_post_ids_skipped": raw_line_count - invalid_records - n_raw,
        "n_after_dedup": n_after_dedup,
        "n_after_spam": n_after_spam,
        "n_after_short": n_after_short,
        "n_kept": n_kept,
        "n_duplicates": duplicate_count,
        "n_spam": sum(bool(doc["is_spam"]) for doc in docs),
        "n_short": sum(bool(doc["is_short"]) for doc in docs),
        "ratio_posts_without_diacritics": round(no_diacritics_count / doc_count, 6)
        if doc_count
        else 0.0,
        "ratio_posts_with_teencode": round(teencode_docs / doc_count, 6)
        if doc_count
        else 0.0,
        "ratio_code_mixed": round(code_mixed_docs / doc_count, 6) if doc_count else 0.0,
        "oov_ratio_english": oov_ratio,
        "top_30_oov_tokens": (
            oov_counter.most_common(30) if vocabulary_available else []
        ),
        "oov_reference_available": vocabulary_available,
        "length_distribution_tokens": length_distribution,
        "token_quality": _token_quality_metrics(docs),
        "domain_stopword_candidates": domain_candidates,
        "step_seconds": {key: round(value, 6) for key, value in step_seconds.items()},
        "ablation_seconds": round(ablation_seconds, 6),
        "pipeline_seconds": round(pipeline_seconds, 6),
        "ablation": ablation,
        "dedup_method": dedup_method,
        "resources": resource_metadata,
        "notes": [
            "No optional NLP corpus is downloaded automatically.",
            (
                "If the NLTK English words corpus is absent, OOV ratio is null "
                "rather than fabricated."
            ),
            (
                "Vietnamese stems/lemmas are identity copies; morphology is only "
                "for eligible English tokens."
            ),
            "Ablation intentionally has 3 configurations for the 48-hour scope.",
        ],
    }

    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Parquet output requires pandas and pyarrow; install `pip install -e .`."
        ) from exc

    for doc in docs:
        doc["source"] = normalize_source(doc.get("source"))
        raw_text = str(doc.get("text_raw", ""))
        safe_text = scrub_pii(raw_text)
        doc["text_raw"] = re.sub(r"(?<!\w)@[A-Za-z0-9_.]+", "<USER>", safe_text)
        doc.pop("source_file", None)
        doc.pop("text_normalized", None)
        doc.pop("n_email", None)
        doc.pop("n_phone", None)
        doc.pop("n_mention", None)
        doc.pop("n_repeated_runs", None)
        doc.pop("english_morphology_available", None)
        doc.pop("uppercase_ratio", None)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.stem}.tmp.parquet")
    frame = pd.DataFrame(docs)
    for column in OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[OUTPUT_COLUMNS]
    try:
        frame.to_parquet(temp_output, index=False, engine="pyarrow")
    except ImportError as exc:
        raise RuntimeError(
            "Parquet output requires pyarrow; install with `pip install -e '.[dev]'`."
        ) from exc
    temp_output.replace(output)
    write_metrics("preprocess", metrics, data_dir)
    return PreprocessResult(
        input_files=len(input_files),
        raw_records=n_raw,
        output_records=len(docs),
        invalid_records=invalid_records,
        output_path=output,
        metrics_path=metrics_path,
    )
