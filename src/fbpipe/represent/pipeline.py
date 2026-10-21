"""Create BoW, TF-IDF, and optional multilingual E5 representations."""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from fbpipe.metrics import write_metrics


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _tokens_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list | tuple | np.ndarray):
        return " ".join(str(token) for token in value if str(token).strip())
    return ""


def _vectorize(
    texts: list[str],
    *,
    min_df: int | float,
    max_df: int | float,
    ngram_range: tuple[int, int],
    sublinear_tf: bool = False,
) -> tuple[Any, Any, bool]:
    """Build one sparse matrix, retrying permissive thresholds for tiny corpora."""
    vectorizer_type = TfidfVectorizer if sublinear_tf else CountVectorizer
    kwargs: dict[str, Any] = {
        "min_df": min_df,
        "max_df": max_df,
        "ngram_range": ngram_range,
        "lowercase": False,
        "token_pattern": r"(?u)\b\w+\b",
    }
    if sublinear_tf:
        kwargs["sublinear_tf"] = True
        kwargs["norm"] = "l2"
    try:
        vectorizer = vectorizer_type(**kwargs)
        matrix = vectorizer.fit_transform(texts)
        return vectorizer, matrix, False
    except ValueError as exc:
        message = str(exc).lower()
        if not any(
            marker in message
            for marker in (
                "empty vocabulary",
                "no terms remain",
                "max_df corresponds to < documents than min_df",
            )
        ):
            raise
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.update(min_df=1, max_df=1.0)
        vectorizer = vectorizer_type(**fallback_kwargs)
        try:
            matrix = vectorizer.fit_transform(texts)
            return vectorizer, matrix, True
        except ValueError as fallback_exc:
            fallback_message = str(fallback_exc).lower()
            if not any(
                marker in fallback_message
                for marker in ("empty vocabulary", "no terms remain")
            ):
                raise
            empty = sparse.csr_matrix((len(texts), 0), dtype=np.float64)
            return None, empty, True


def build_classical_representations(
    frame: pd.DataFrame, settings: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build deterministic sparse BoW and TF-IDF matrices for the given documents."""
    config = settings or {}
    bow_config = config.get("bow", {}) or {}
    tfidf_config = config.get("tfidf", {}) or {}
    texts = [_tokens_to_text(value) for value in frame.get("tokens_nostop", [])]
    if not texts and len(frame):
        texts = [str(value or "") for value in frame.get("text_clean", [])]

    ngram_value = bow_config.get("ngram", [1, 2])
    ngram_range = (int(ngram_value[0]), int(ngram_value[1]))
    min_df = bow_config.get("min_df", 3)
    max_df = bow_config.get("max_df", 0.8)
    bow_vectorizer, bow, bow_fallback = _vectorize(
        texts,
        min_df=min_df,
        max_df=max_df,
        ngram_range=ngram_range,
    )
    tfidf_ngram = tfidf_config.get("ngram", ngram_value)
    tfidf_vectorizer, tfidf, tfidf_fallback = _vectorize(
        texts,
        min_df=tfidf_config.get("min_df", min_df),
        max_df=tfidf_config.get("max_df", max_df),
        ngram_range=(int(tfidf_ngram[0]), int(tfidf_ngram[1])),
        sublinear_tf=bool(tfidf_config.get("sublinear_tf", True)),
    )

    bow_terms = (
        bow_vectorizer.get_feature_names_out().tolist()
        if bow_vectorizer is not None
        else []
    )
    tfidf_terms = (
        tfidf_vectorizer.get_feature_names_out().tolist()
        if tfidf_vectorizer is not None
        else []
    )
    total_tokens: list[str] = []
    for value in frame.get("tokens_nostop", []):
        if isinstance(value, list | tuple | np.ndarray):
            total_tokens.extend(str(token) for token in value)
        else:
            total_tokens.extend(str(value or "").split())
    term_counts: dict[str, int] = {}
    for token in total_tokens:
        key = str(token)
        term_counts[key] = term_counts.get(key, 0) + 1
    top_tf = sorted(term_counts.items(), key=lambda item: (-item[1], item[0]))[:20]
    tfidf_mean = (
        np.asarray(tfidf.mean(axis=0)).ravel() if tfidf.shape[1] else np.array([])
    )
    top_tfidf_idx = np.argsort(-tfidf_mean)[:20]
    top_tfidf = [
        {
            "term": tfidf_terms[int(index)],
            "mean_tfidf": round(float(tfidf_mean[index]), 8),
        }
        for index in top_tfidf_idx
    ]
    return {
        "bow": bow.tocsr(),
        "tfidf": tfidf.tocsr(),
        "bow_terms": bow_terms,
        "tfidf_terms": tfidf_terms,
        "bow_fallback_thresholds": bow_fallback,
        "tfidf_fallback_thresholds": tfidf_fallback,
        "top_tf": [{"term": term, "count": count} for term, count in top_tf],
        "top_tfidf": top_tfidf,
    }


def _sparse_stats(matrix: Any, terms: list[str], path: Path) -> dict[str, Any]:
    total = int(matrix.shape[0] * matrix.shape[1])
    nonzero = int(matrix.nnz)
    return {
        "rows": int(matrix.shape[0]),
        "dimensions": int(matrix.shape[1]),
        "vocabulary_size": len(terms),
        "nnz": nonzero,
        "density": round(nonzero / total, 8) if total else 0.0,
        "sparsity": round(1 - nonzero / total, 8) if total else 1.0,
        "artifact_bytes": path.stat().st_size if path.exists() else 0,
    }


def _e5_embeddings(
    texts: list[str],
    *,
    cache_path: Path,
    cache_meta_path: Path,
    cache_key: str,
    model_name: str,
    prefix: str,
    batch_size: int,
    force: bool,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Load E5 lazily; cache vectors and skip gracefully on optional failures."""
    if not force and cache_path.exists() and cache_meta_path.exists():
        try:
            cache_meta = json.loads(cache_meta_path.read_text(encoding="utf-8"))
            cached = np.load(cache_path, allow_pickle=False)
            if (
                cache_meta.get("cache_key") == cache_key
                and cached.ndim == 2
                and cached.shape[0] == len(texts)
            ):
                return cached, {
                    "available": True,
                    "cached": True,
                    "model": model_name,
                    "dimensions": int(cached.shape[1]) if cached.ndim == 2 else 0,
                    "cache_file": str(cache_path),
                }
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    # Never leave a stale vector file that downstream evaluation could mistake
    # for embeddings produced from the current corpus/configuration.
    cache_path.unlink(missing_ok=True)
    cache_meta_path.unlink(missing_ok=True)

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # Optional dependency/model must not block BoW/TF-IDF.
        message = (
            "E5 skipped: sentence-transformers is unavailable; install it with "
            "`python -m pip install -e '.[embed]'`."
        )
        warnings.warn(f"{message} Cause: {exc}", RuntimeWarning, stacklevel=2)
        return None, {"available": False, "cached": False, "warning": message}

    try:
        model = SentenceTransformer(model_name)
        vectors = model.encode(
            [f"{prefix}{text}" for text in texts],
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        embeddings = np.asarray(vectors, dtype=np.float32)
        if embeddings.ndim != 2 or embeddings.shape[0] != len(texts):
            raise ValueError(f"Unexpected E5 output shape: {embeddings.shape}")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, embeddings, allow_pickle=False)
        cache_meta_path.write_text(
            json.dumps(
                {"cache_key": cache_key, "model": model_name, "rows": len(texts)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return embeddings, {
            "available": True,
            "cached": False,
            "model": model_name,
            "dimensions": int(embeddings.shape[1]),
            "cache_file": str(cache_path),
        }
    except Exception as exc:  # model download/load failures are optional too
        message = (
            "E5 skipped because the model could not load or encode: "
            f"{type(exc).__name__}: {exc}"
        )
        warnings.warn(message, RuntimeWarning, stacklevel=2)
        return None, {
            "available": False,
            "cached": False,
            "warning": message,
            "model": model_name,
        }


def represent_corpus(
    *,
    input_path: str | Path = "data/silver/documents.parquet",
    output_dir: str | Path = "data/gold",
    data_dir: str | Path = "data",
    settings: dict[str, Any] | None = None,
    include_e5: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Write reusable BoW/TF-IDF matrices and optional cached E5 embeddings."""
    source = Path(input_path)
    destination = Path(output_dir)
    if not source.exists():
        raise FileNotFoundError(
            f"Missing Silver Parquet input: {source}; run `fbpipe preprocess` first."
        )
    config = settings or {}
    source_hash = _sha256_file(source)
    config_hash = _stable_hash({"represent": config, "include_e5": include_e5})
    manifest_path = destination / "representations.json"
    artifact_paths = [
        destination / "bow.npz",
        destination / "tfidf.npz",
        destination / "vocab.json",
        destination / "doc_ids.json",
    ]
    if (
        not force
        and manifest_path.exists()
        and all(path.exists() for path in artifact_paths)
    ):
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            e5_is_satisfied = (
                not include_e5 or (destination / "e5_embeddings.npy").exists()
            )
            if (
                previous.get("input_sha256") == source_hash
                and previous.get("settings_sha256") == config_hash
                and e5_is_satisfied
            ):
                return {
                    **previous.get("metrics", {}),
                    "skipped_as_up_to_date": True,
                    "output_dir": str(destination),
                }
        except (OSError, json.JSONDecodeError):
            pass

    frame = pd.read_parquet(source)
    if "doc_id" not in frame.columns:
        raise ValueError("Silver Parquet must contain a `doc_id` column.")
    if "tokens_nostop" not in frame.columns:
        raise ValueError("Silver Parquet must contain `tokens_nostop` from Phase 2.")
    destination.mkdir(parents=True, exist_ok=True)
    classical = build_classical_representations(frame, config)
    sparse.save_npz(destination / "bow.npz", classical["bow"])
    sparse.save_npz(destination / "tfidf.npz", classical["tfidf"])
    (destination / "vocab.json").write_text(
        json.dumps(
            {"bow": classical["bow_terms"], "tfidf": classical["tfidf_terms"]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    doc_ids = frame["doc_id"].fillna("").astype(str).tolist()
    (destination / "doc_ids.json").write_text(
        json.dumps(doc_ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    bow_stats = _sparse_stats(
        classical["bow"], classical["bow_terms"], destination / "bow.npz"
    )
    tfidf_stats = _sparse_stats(
        classical["tfidf"], classical["tfidf_terms"], destination / "tfidf.npz"
    )
    fallback_thresholds = (
        ("bow", classical["bow_fallback_thresholds"]),
        ("tfidf", classical["tfidf_fallback_thresholds"]),
    )
    for key, value in fallback_thresholds:
        if value:
            warnings.warn(
                f"{key.upper()} used permissive min_df/max_df because the corpus "
                "was small or filtered empty.",
                RuntimeWarning,
                stacklevel=2,
            )

    transformer_config = config.get("transformer", {}) or {}
    text_clean = (
        frame.get("text_clean", pd.Series([""] * len(frame)))
        .fillna("")
        .astype(str)
        .tolist()
    )
    model_name = str(transformer_config.get("model", "intfloat/multilingual-e5-small"))
    prefix = str(transformer_config.get("prefix", "query: "))
    batch_size = int(transformer_config.get("batch_size", 64))
    cache_key = _stable_hash(
        {
            "doc_ids": doc_ids,
            "text_clean": text_clean,
            "model": model_name,
            "prefix": prefix,
        }
    )
    e5_matrix: np.ndarray | None = None
    e5_metrics: dict[str, Any] = {
        "available": False,
        "cached": False,
        "skipped_by_user": not include_e5,
    }
    if include_e5:
        e5_matrix, e5_metrics = _e5_embeddings(
            text_clean,
            cache_path=destination / "e5_embeddings.npy",
            cache_meta_path=destination / "e5_cache.json",
            cache_key=cache_key,
            model_name=model_name,
            prefix=prefix,
            batch_size=batch_size,
            force=force,
        )
    elif (destination / "e5_embeddings.npy").exists():
        (destination / "e5_embeddings.npy").unlink()
        (destination / "e5_cache.json").unlink(missing_ok=True)

    metrics: dict[str, Any] = {
        "input_path": str(source),
        "n_documents": len(frame),
        "output_dir": str(destination),
        "bow": bow_stats,
        "tfidf": tfidf_stats,
        "bow_used_fallback_thresholds": classical["bow_fallback_thresholds"],
        "tfidf_used_fallback_thresholds": classical["tfidf_fallback_thresholds"],
        "top_tf_terms": classical["top_tf"],
        "top_tfidf_terms": classical["top_tfidf"],
        "e5": e5_metrics,
        "seed": 42,
    }
    manifest = {
        "input_sha256": source_hash,
        "settings_sha256": config_hash,
        "metrics": metrics,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_metrics(
        "represent",
        {**metrics, "input_sha256": source_hash, "settings_sha256": config_hash},
        data_dir,
    )
    return metrics
