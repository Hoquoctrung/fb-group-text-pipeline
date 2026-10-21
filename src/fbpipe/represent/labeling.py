"""Human-label sampling and clearly flagged rule-based proxy evaluation."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from fbpipe.metrics import write_metrics

TAXONOMY = (
    "hoi_dap",
    "chia_se",
    "thong_bao",
    "tim_kiem_tuyen_dung",
    "quang_cao_spam",
    "khac",
)


def _tokens(value: Any) -> list[str]:
    if isinstance(value, list | tuple | np.ndarray):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return value.split()
    return []


def _length(row: Any) -> int:
    tokens = _tokens(row.get("tokens_nostop", []))
    if tokens:
        return len(tokens)
    return len(str(row.get("text_clean") or "").split())


def stratified_sample(
    frame: pd.DataFrame, n: int = 200, seed: int = 42
) -> pd.DataFrame:
    """Sample approximately proportionally by month and text-length quartile."""
    if n < 1:
        raise ValueError("Sample size n must be >= 1.")
    if frame.empty:
        return frame.copy()
    if "doc_id" not in frame.columns:
        raise ValueError("Input Silver Parquet must contain `doc_id`.")
    work = frame.copy().reset_index(drop=True)
    work["_month_stratum"] = (
        work.get("year_month", pd.Series(["unknown"] * len(work)))
        .fillna("unknown")
        .astype(str)
    )
    work["_length_value"] = [_length(row) for _, row in work.iterrows()]
    n_bins = min(4, len(work))
    ranks = work["_length_value"].rank(method="first")
    work["_length_stratum"] = (
        pd.qcut(ranks, q=n_bins, labels=False, duplicates="drop").fillna(0).astype(int)
    )
    grouped = list(
        work.groupby(["_month_stratum", "_length_stratum"], dropna=False, sort=True)
    )
    target = min(n, len(work))
    exact = [target * len(group) / len(work) for _, group in grouped]
    allocation = [
        min(len(group), int(value))
        for value, (_, group) in zip(exact, grouped, strict=True)
    ]
    remaining = target - sum(allocation)
    order = sorted(
        range(len(grouped)),
        key=lambda index: (-(exact[index] - int(exact[index])), index),
    )
    while remaining > 0:
        progressed = False
        for index in order:
            if allocation[index] < len(grouped[index][1]):
                allocation[index] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            break

    pieces: list[pd.DataFrame] = []
    for index, ((_, group), amount) in enumerate(zip(grouped, allocation, strict=True)):
        if amount:
            pieces.append(group.sample(n=amount, random_state=seed + index))
    sampled = pd.concat(pieces, ignore_index=True) if pieces else work.iloc[0:0].copy()
    sampled = sampled.sample(frac=1, random_state=seed).reset_index(drop=True)
    sampled["text_clean_preview"] = (
        sampled.get(
            "text_clean", sampled.get("text_raw", pd.Series([""] * len(sampled)))
        )
        .fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.slice(0, 600)
    )
    result = sampled[["doc_id", "text_clean_preview"]].copy()
    result["label"] = ""
    return result


def sample_label_file(
    *,
    input_path: str | Path,
    output_path: str | Path,
    n: int = 200,
    seed: int = 42,
    force: bool = False,
) -> dict[str, Any]:
    """Create a label CSV without overwriting human labels by default."""
    source = Path(input_path)
    destination = Path(output_path)
    if not source.exists():
        raise FileNotFoundError(
            f"Missing Silver Parquet: {source}; run `fbpipe preprocess` first."
        )
    if destination.exists() and not force:
        raise FileExistsError(
            f"Label file exists: {destination}; use --force only if you "
            "want to replace it."
        )
    frame = pd.read_parquet(source)
    sampled = stratified_sample(frame, n=n, seed=seed)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sampled.to_csv(destination, index=False, encoding="utf-8-sig")
    if len(sampled) < n:
        warnings.warn(
            f"Requested {n} labels but only {len(sampled)} documents are available.",
            RuntimeWarning,
            stacklevel=2,
        )
    return {
        "input_path": str(source),
        "output_path": str(destination),
        "requested_n": n,
        "sampled_n": len(sampled),
        "seed": seed,
        "stratification": ["year_month", "text-length quartile"],
        "taxonomy": list(TAXONOMY),
    }


def weak_label(text: str) -> str:
    """Apply transparent high-level rules; output is a proxy, never a human label."""
    value = str(text or "").casefold()
    hiring_terms = (
        "tuyển dụng",
        "tuyển gấp",
        "tìm việc",
        "việc làm",
        "ứng tuyển",
        "hiring",
        "job opening",
    )
    if any(term in value for term in hiring_terms):
        return "tim_kiem_tuyen_dung"
    spam_terms = (
        "giá rẻ",
        "sale",
        "mua ngay",
        "inbox",
        "liên hệ ngay",
        "quảng cáo",
        "zalo",
        "khuyến mãi",
    )
    if any(term in value for term in spam_terms):
        return "quang_cao_spam"
    notice_terms = (
        "thông báo",
        "lịch trình",
        "lịch học",
        "kính mời",
        "trân trọng thông báo",
        "ngày mai",
    )
    if any(term in value for term in notice_terms):
        return "thong_bao"
    question_terms = (
        "cho hỏi",
        "ai biết",
        "có ai",
        "làm sao",
        "giúp mình",
        "help me",
        "anyone know",
    )
    if "?" in value or any(term in value for term in question_terms):
        return "hoi_dap"
    sharing_terms = (
        "chia sẻ",
        "kinh nghiệm",
        "mình đã",
        "review",
        "hướng dẫn",
        "câu chuyện",
    )
    if any(term in value for term in sharing_terms):
        return "chia_se"
    return "khac"


def build_proxy_labels(frame: pd.DataFrame) -> pd.DataFrame:
    """Assign weak rules to all rows and mark every generated label as proxy."""
    text_column = "text_clean" if "text_clean" in frame.columns else "text_raw"
    labels = pd.DataFrame({"doc_id": frame["doc_id"].astype(str)})
    labels["label"] = frame[text_column].fillna("").astype(str).map(weak_label)
    labels["proxy_labels"] = True
    return labels


def _load_feature_matrices(represent_dir: Path) -> tuple[list[str], dict[str, Any]]:
    from scipy.sparse import load_npz

    ids_path = represent_dir / "doc_ids.json"
    if not ids_path.exists():
        raise FileNotFoundError(
            f"Missing representation index {ids_path}; run `fbpipe represent` first."
        )
    doc_ids = json.loads(ids_path.read_text(encoding="utf-8"))
    matrices: dict[str, Any] = {}
    for name in ("bow", "tfidf"):
        path = represent_dir / f"{name}.npz"
        if path.exists():
            matrices[name] = load_npz(path)
    e5_path = represent_dir / "e5_embeddings.npy"
    if e5_path.exists():
        matrices["e5"] = np.load(e5_path, allow_pickle=False)
    return [str(doc_id) for doc_id in doc_ids], matrices


def _macro_f1_for_matrix(
    matrix: Any, labels: list[str], seed: int = 42
) -> dict[str, Any]:
    """Measure stratified out-of-fold macro-F1, or explain why it is not measurable."""
    counts = pd.Series(labels).value_counts()
    classes = int(len(counts))
    if classes < 2 or not len(labels) or int(counts.min()) < 2:
        return {
            "macro_f1": None,
            "cv_folds": 0,
            "reason": "Need at least two classes with two labeled examples each.",
        }
    n_splits = min(5, int(counts.min()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    estimator = LogisticRegression(
        max_iter=1000, class_weight="balanced", random_state=seed
    )
    try:
        predictions = cross_val_predict(
            estimator, matrix, np.asarray(labels), cv=cv, method="predict"
        )
    except (ValueError, TypeError) as exc:
        return {"macro_f1": None, "cv_folds": n_splits, "reason": str(exc)}
    return {
        "macro_f1": round(
            float(f1_score(labels, predictions, average="macro", zero_division=0)), 6
        ),
        "cv_folds": n_splits,
        "reason": None,
    }


def evaluate_labels(
    *,
    input_path: str | Path,
    labels_path: str | Path,
    represent_dir: str | Path,
    data_dir: str | Path = "data",
    seed: int = 42,
) -> dict[str, Any]:
    """Evaluate representations using hand labels or flagged proxy labels."""
    source = Path(input_path)
    manual_path = Path(labels_path)
    representation_path = Path(represent_dir)
    if not source.exists():
        raise FileNotFoundError(
            f"Missing Silver Parquet: {source}; run `fbpipe preprocess` first."
        )
    frame = pd.read_parquet(source)
    manual_labels: pd.DataFrame | None = None
    if manual_path.exists():
        candidate = pd.read_csv(
            manual_path, dtype={"doc_id": str}, keep_default_na=False
        )
        if {"doc_id", "label"}.issubset(candidate.columns):
            candidate["label"] = candidate["label"].astype(str).str.strip()
            candidate = candidate[candidate["label"] != ""]
            if not candidate.empty:
                manual_labels = candidate[["doc_id", "label"]].drop_duplicates("doc_id")

    proxy_labels = manual_labels is None
    if proxy_labels:
        labels_frame = build_proxy_labels(frame)
        proxy_output = Path(data_dir) / "labels" / "proxy_labels.csv"
        proxy_output.parent.mkdir(parents=True, exist_ok=True)
        labels_frame.to_csv(proxy_output, index=False, encoding="utf-8-sig")
        warnings.warn(
            "No hand labels found; evaluating against rule-based proxy labels. "
            "Metrics are diagnostic only and must be reported with proxy_labels=true.",
            RuntimeWarning,
            stacklevel=2,
        )
    else:
        labels_frame = manual_labels.copy()
        labels_frame["proxy_labels"] = False

    doc_ids, matrices = _load_feature_matrices(representation_path)
    if not matrices:
        raise FileNotFoundError(
            f"No BoW/TF-IDF/E5 matrices found under {representation_path}; "
            "run `fbpipe represent` first."
        )
    matrix_index = {doc_id: index for index, doc_id in enumerate(doc_ids)}
    labels_frame["doc_id"] = labels_frame["doc_id"].astype(str)
    labels_frame = labels_frame[labels_frame["doc_id"].isin(matrix_index)].copy()
    labels_frame = labels_frame.drop_duplicates("doc_id")
    row_indices = [matrix_index[doc_id] for doc_id in labels_frame["doc_id"]]
    target_labels = labels_frame["label"].astype(str).tolist()
    results: dict[str, Any] = {}
    for name, matrix in matrices.items():
        if len(row_indices) == 0:
            score = {
                "macro_f1": None,
                "cv_folds": 0,
                "reason": "No labels aligned to representation doc IDs.",
            }
        else:
            sliced = matrix[row_indices]
            score = _macro_f1_for_matrix(sliced, target_labels, seed=seed)
        results[name] = {
            **score,
            "n_labeled": len(row_indices),
            "proxy_labels": proxy_labels,
        }

    metrics = {
        "input_path": str(source),
        "labels_path": (
            str(manual_path)
            if not proxy_labels
            else str(Path(data_dir) / "labels" / "proxy_labels.csv")
        ),
        "n_labeled": len(row_indices),
        "n_classes": len(set(target_labels)),
        "proxy_labels": proxy_labels,
        "label_source": "rule_based_proxy" if proxy_labels else "human_csv",
        "results": results,
        "seed": seed,
        "taxonomy": list(TAXONOMY),
    }
    write_metrics("label_eval", metrics, data_dir)
    return metrics
