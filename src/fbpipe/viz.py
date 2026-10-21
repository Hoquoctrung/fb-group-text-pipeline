"""Matplotlib figures for Phase 5's first, fast visualization slice."""

from __future__ import annotations

import json
import math
import re
import unicodedata
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from fbpipe.analysis import analyze_corpus, load_silver, source_caption

FIGURE_NAMES = (
    "F01_daily_posts.png",
    "F03_length_distribution.png",
    "F06_top_terms_tf_tfidf.png",
    "F07_word_cloud.png",
    "F09_lda_coherence.png",
    "F10_lda_topics.png",
    "F11_embedding_map.png",
    "F13_representation_comparison.png",
    "F14_storage_benchmark.png",
    "F15_preprocess_funnel.png",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _pyplot() -> Any:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Figure generation needs matplotlib; install with "
            "`python -m pip install -e '.[viz]'`."
        ) from exc
    plt.rcParams["font.family"] = "DejaVu Sans"
    return plt


def _finish(
    plt: Any,
    figure: Any,
    path: Path,
    caption: str,
    *,
    bottom: float = 0.18,
) -> None:
    figure.text(
        0.01,
        0.025,
        caption,
        ha="left",
        va="bottom",
        fontsize=8,
        wrap=True,
    )
    # Avoid tight_layout's incompatibility warning for nested GridSpec axes (F10).
    # Fixed subplot margins keep title and footer separated across all figure types.
    figure.subplots_adjust(left=0.09, right=0.98, top=0.88, bottom=bottom)
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def _placeholder(axis: Any, message: str) -> None:
    axis.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    axis.set_axis_off()


def _draw_f01(plt: Any, frame: pd.DataFrame, out: Path, caption: str) -> None:
    figure, axis = plt.subplots(figsize=(10, 5))
    dates = pd.to_datetime(
        frame.get("created_at", pd.Series(index=frame.index, dtype="object")),
        errors="coerce",
        utc=True,
    )
    counts = dates.dropna().dt.strftime("%Y-%m-%d").value_counts().sort_index()
    if counts.empty:
        _placeholder(axis, "Chưa có timestamp hợp lệ trong Silver.")
    else:
        axis.bar(counts.index.tolist(), counts.values.tolist(), width=0.8)
        axis.set_xlabel("Ngày")
        axis.set_ylabel("Số bài")
        axis.tick_params(axis="x", rotation=55)
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("F01 — Số bài theo ngày")
    _finish(plt, figure, out / "F01_daily_posts.png", caption)


def _draw_f03(plt: Any, analysis: dict[str, Any], out: Path, caption: str) -> None:
    figure, axis = plt.subplots(figsize=(8, 5))
    lengths = [int(value) for value in analysis.get("lengths_tokens", [])]
    if not lengths:
        _placeholder(axis, "Chưa có độ dài token để vẽ.")
    else:
        axis.hist(lengths, bins=min(30, max(5, len(set(lengths)))), edgecolor="black")
        axis.set_xlabel("Số token mỗi bài")
        axis.set_ylabel("Số bài")
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("F03 — Phân bố độ dài bài")
    _finish(plt, figure, out / "F03_length_distribution.png", caption)


def _draw_f06(plt: Any, analysis: dict[str, Any], out: Path, caption: str) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 6))
    comparisons = (
        (axes[0], analysis.get("top_tf_terms", []), "count", "Top term theo TF"),
        (
            axes[1],
            analysis.get("top_tfidf_terms", []),
            "mean_tfidf",
            "Top term theo TF-IDF",
        ),
    )
    for axis, rows, score_key, title in comparisons:
        selected = rows[:15] if isinstance(rows, list) else []
        selected = [row for row in selected if isinstance(row, dict)]
        selected.reverse()
        if not selected:
            _placeholder(axis, "Chưa có metrics thuật ngữ; chạy `fbpipe analyze`.")
            continue
        labels = [str(row.get("term", "?")) for row in selected]
        scores = [float(row.get(score_key, 0.0) or 0.0) for row in selected]
        axis.barh(labels, scores)
        axis.set_title(title)
        axis.grid(axis="x", alpha=0.2)
    figure.suptitle("F06 — So sánh thuật ngữ TF và TF-IDF")
    _finish(plt, figure, out / "F06_top_terms_tf_tfidf.png", caption, bottom=0.16)


_WORD_RE = re.compile(r"[^\W\d_][\w'’\-]*", flags=re.UNICODE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<!\w)@[\w.]+", re.UNICODE)
_PHONE_RE = re.compile(r"(?<!\d)\+?\d[\d .()\-]{6,}\d(?!\d)")


def _as_tokens(value: Any) -> list[str]:
    """Convert Silver's token representation to a plain list of strings."""
    if isinstance(value, str):
        return value.split()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list | tuple):
        return [str(token) for token in value if str(token).strip()]
    return []


def _term_key(value: str) -> str:
    """Normalize punctuation and case while preserving Vietnamese accents."""
    return value.strip(".,:;!?()[]{}<>\"'`“”‘’").casefold()


def _matching_key(value: str) -> str:
    """Return an accent-insensitive key used only for sensitive-term matching."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _sensitive_terms(frame: pd.DataFrame) -> set[str]:
    """Collect terms belonging to detectable PII spans from raw/cased text."""
    blocked: set[str] = set()
    for column in ("text_raw", "text_cased", "text_clean"):
        if column not in frame.columns:
            continue
        for value in frame[column].dropna().astype(str):
            for pattern in (_EMAIL_RE, _URL_RE, _MENTION_RE, _PHONE_RE):
                for match in pattern.finditer(value):
                    blocked.update(
                        key
                        for key in (
                            _matching_key(token)
                            for token in _WORD_RE.findall(match.group())
                        )
                        if key
                    )
    return blocked


def _heuristic_name_terms(frame: pd.DataFrame) -> set[str]:
    """Find multiword title-case runs as a conservative proper-name heuristic.

    This is not named-entity recognition. It deliberately targets consecutive
    capitalized words, and the figure caption reports that this heuristic is used.
    """
    blocked: set[str] = set()
    if "text_cased" not in frame.columns:
        return blocked
    for value in frame["text_cased"].dropna().astype(str):
        run: list[str] = []
        previous_end = 0
        for match in _WORD_RE.finditer(value):
            token = match.group()
            between = value[previous_end : match.start()]
            if re.search(r"[.!?\n]", between):
                if len(run) >= 2:
                    blocked.update(_matching_key(item) for item in run)
                run = []
            title_case = token[:1].isupper() and (
                len(token) == 1 or token[1:].islower()
            )
            if title_case:
                run.append(_term_key(token))
            else:
                if len(run) >= 2:
                    blocked.update(_matching_key(item) for item in run)
                run = []
            previous_end = match.end()
        if len(run) >= 2:
            blocked.update(_matching_key(item) for item in run)
    return {term for term in blocked if term}


def _looks_like_pii_token(token: str) -> bool:
    candidate = token.strip()
    if not candidate:
        return True
    return bool(
        _EMAIL_RE.search(candidate)
        or _URL_RE.search(candidate)
        or _MENTION_RE.search(candidate)
        or _PHONE_RE.fullmatch(candidate)
        or re.fullmatch(r"\d{4,}", candidate)
        or re.fullmatch(r"(?i)(?:pii|phone|email|sdt)[_\-\d]*", candidate)
    )


def _wordcloud_frequencies(frame: pd.DataFrame) -> dict[str, int]:
    """Return filtered token counts; PII filtering and name filtering are heuristic."""
    sensitive = _sensitive_terms(frame)
    names = _heuristic_name_terms(frame)
    counts: Counter[str] = Counter()
    if "tokens_nostop" not in frame.columns:
        return {}
    for value in frame["tokens_nostop"]:
        for token in _as_tokens(value):
            term = _term_key(token)
            if (
                len(term) < 2
                or _looks_like_pii_token(token)
                or _matching_key(term) in sensitive
                or _matching_key(term) in names
                or not re.search(r"[^\W\d_]", term, flags=re.UNICODE)
            ):
                continue
            counts[term] += 1
    return dict(counts)


def _draw_f07(plt: Any, frame: pd.DataFrame, out: Path, caption: str) -> None:
    figure, axis = plt.subplots(figsize=(12, 7))
    frequencies = _wordcloud_frequencies(frame)
    if not frequencies:
        _placeholder(axis, "Không còn token đủ điều kiện sau lọc PII/tên riêng.")
    else:
        try:
            from matplotlib import font_manager
            from wordcloud import WordCloud
        except ImportError:
            warnings.warn(
                "F07 needs WordCloud; install `python -m pip install -e '.[viz]'`.",
                RuntimeWarning,
                stacklevel=2,
            )
            _placeholder(axis, "Thiếu `wordcloud`; cài extra [viz] để tạo F07.")
        else:
            font_path = font_manager.findfont("DejaVu Sans", fallback_to_default=True)
            cloud = WordCloud(
                width=1200,
                height=700,
                background_color="white",
                font_path=font_path,
                max_words=120,
                collocations=False,
                random_state=42,
            ).generate_from_frequencies(frequencies)
            axis.imshow(cloud, interpolation="bilinear")
            axis.set_axis_off()
    figure.suptitle("F07 — Word cloud (đã lọc PII và tên riêng theo heuristic)")
    _finish(
        plt,
        figure,
        out / "F07_word_cloud.png",
        f"{caption}. Lọc PII theo regex; tên riêng là heuristic trên "
        "text_cased, không phải NER.",
        bottom=0.14,
    )


def _draw_f10(plt: Any, data_dir: Path, out: Path, caption: str) -> None:
    """Fit a small sklearn LDA sweep on the saved sparse BoW matrix."""
    figure: Any
    try:
        from scipy import sparse
        from sklearn.decomposition import LatentDirichletAllocation

        matrix_path = data_dir / "gold" / "bow.npz"
        vocab_path = data_dir / "gold" / "vocab.json"
        if not matrix_path.is_file() or not vocab_path.is_file():
            raise FileNotFoundError(
                "Missing data/gold/bow.npz or vocab.json; run "
                "`fbpipe represent --skip-e5` first."
            )
        matrix = sparse.load_npz(matrix_path).tocsr()
        vocabulary_data = json.loads(vocab_path.read_text(encoding="utf-8"))
        terms = (
            vocabulary_data.get("bow", []) if isinstance(vocabulary_data, dict) else []
        )
        if not isinstance(terms, list) or len(terms) != matrix.shape[1]:
            raise ValueError(
                "BoW vocabulary does not match the saved matrix dimensions."
            )
        max_k = min(8, matrix.shape[0], matrix.shape[1])
        candidates = list(range(3, max_k + 1))
        if not candidates or matrix.nnz == 0:
            raise ValueError("BoW is too small or empty for LDA with k=3..8.")

        fitted: list[tuple[int, float, Any]] = []
        for k in candidates:
            model = LatentDirichletAllocation(
                n_components=k,
                max_iter=5,
                learning_method="batch",
                evaluate_every=-1,
                random_state=42,
                n_jobs=1,
            )
            model.fit(matrix)
            perplexity = float(model.perplexity(matrix))
            if math.isfinite(perplexity):
                fitted.append((k, perplexity, model))
        if not fitted:
            raise ValueError("LDA did not produce finite perplexity for k=3..8.")
        best_k, best_perplexity, best_model = min(fitted, key=lambda item: item[1])
        prevalence = best_model.transform(matrix).mean(axis=0)
    except ImportError:
        figure, axis = plt.subplots(figsize=(8, 5))
        _placeholder(axis, "Thiếu scikit-learn/scipy để chạy LDA trên ma trận BoW.")
        figure.suptitle("F10 — Chủ đề LDA (không khả dụng)")
        _finish(plt, figure, out / "F10_lda_topics.png", caption)
        return
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        figure, axis = plt.subplots(figsize=(8, 5))
        _placeholder(axis, str(exc))
        figure.suptitle("F10 — Chủ đề LDA (chưa có kết quả)")
        _finish(plt, figure, out / "F10_lda_topics.png", caption)
        return

    topic_rows = math.ceil(best_k / 2)
    figure = plt.figure(figsize=(15, max(6.5, topic_rows * 2.4)))
    grid = figure.add_gridspec(
        nrows=topic_rows,
        ncols=3,
        width_ratios=(1.0, 1.15, 1.15),
        wspace=0.55,
        hspace=0.7,
    )
    perplexity_axis = figure.add_subplot(grid[:, 0])
    k_values = [item[0] for item in fitted]
    perplexities = [item[1] for item in fitted]
    perplexity_axis.plot(k_values, perplexities, marker="o")
    perplexity_axis.axvline(best_k, linestyle="--", alpha=0.65)
    perplexity_axis.set_xticks(k_values)
    perplexity_axis.set_xlabel("Số chủ đề k")
    perplexity_axis.set_ylabel("Perplexity (thấp hơn tốt hơn)")
    perplexity_axis.set_title(f"Chọn k={best_k}\nPerplexity={best_perplexity:.2f}")
    perplexity_axis.grid(axis="y", alpha=0.25)

    component_names = list(terms)
    for topic_idx, component in enumerate(best_model.components_):
        axis = figure.add_subplot(grid[topic_idx // 2, 1 + topic_idx % 2])
        top_indices = component.argsort()[::-1][: min(8, len(component))]
        labels = [str(component_names[index]) for index in top_indices][::-1]
        values = [float(component[index]) for index in top_indices][::-1]
        axis.barh(labels, values)
        axis.set_title(f"Topic {topic_idx + 1} · tỷ trọng {prevalence[topic_idx]:.1%}")
        axis.grid(axis="x", alpha=0.2)
    for unused in range(best_k, topic_rows * 2):
        axis = figure.add_subplot(grid[unused // 2, 1 + unused % 2])
        axis.set_axis_off()
    figure.suptitle(
        f"F10 — Chủ đề LDA scikit-learn (k={best_k}, max_iter=5; chọn theo perplexity)"
    )
    _finish(
        plt,
        figure,
        out / "F10_lda_topics.png",
        f"{caption}. LDA trên data/gold/bow.npz; thử k=3..8; "
        "max_iter=5; k chọn theo perplexity nhỏ nhất.",
        bottom=0.12,
    )


def _lda_curve(
    frame: pd.DataFrame,
    data_dir: Path,
) -> tuple[list[int], list[float], str, int | None]:
    """Evaluate k=3..10 with gensim c_v, or sklearn perplexity as fallback."""
    from scipy import sparse
    from sklearn.decomposition import LatentDirichletAllocation

    matrix_path = data_dir / "gold" / "bow.npz"
    vocab_path = data_dir / "gold" / "vocab.json"
    if not matrix_path.is_file() or not vocab_path.is_file():
        raise FileNotFoundError(
            "Missing data/gold/bow.npz or vocab.json; run `fbpipe represent`."
        )
    matrix = sparse.load_npz(matrix_path).tocsr()
    vocabulary_data = json.loads(vocab_path.read_text(encoding="utf-8"))
    terms = vocabulary_data.get("bow", []) if isinstance(vocabulary_data, dict) else []
    if matrix.shape[0] != len(frame):
        raise ValueError("BoW rows do not match Silver rows; rerun `fbpipe represent`.")
    if not isinstance(terms, list) or len(terms) != matrix.shape[1]:
        raise ValueError("BoW vocabulary does not match the saved matrix dimensions.")
    if matrix.shape[1] < 3 or matrix.nnz == 0 or matrix.shape[0] < 2:
        raise ValueError("BoW is too small or empty for an LDA sweep from k=3 to 10.")

    candidates = list(range(3, 11))
    fitted: list[tuple[int, Any, float]] = []
    for k in candidates:
        model = LatentDirichletAllocation(
            n_components=k,
            max_iter=5,
            learning_method="batch",
            evaluate_every=-1,
            random_state=42,
            n_jobs=1,
        )
        model.fit(matrix)
        fitted.append((k, model, float(model.perplexity(matrix))))

    # Gensim is optional. Use c_v only when Dictionary and CoherenceModel both
    # work on this corpus. Any compatibility/corpus failure falls back uniformly
    # to sklearn perplexity rather than mixing measures on one chart.
    coherence_scores: list[float] = []
    try:
        from gensim.corpora import Dictionary
        from gensim.models import CoherenceModel

        token_column = frame.get("tokens_nostop", pd.Series([[]] * len(frame)))
        texts = [_as_tokens(value) for value in token_column]
        texts = [tokens for tokens in texts if tokens]
        dictionary = Dictionary(texts)
        if not texts or len(dictionary) == 0:
            raise ValueError("No tokenized text available for c_v coherence.")
        known_tokens = set(dictionary.token2id)
        for _, model, _ in fitted:
            topic_words: list[list[str]] = []
            for component in model.components_:
                words = [
                    str(terms[index])
                    for index in component.argsort()[::-1]
                    if str(terms[index]) in known_tokens
                    and " " not in str(terms[index])
                ][:10]
                if not words:
                    raise ValueError(
                        "LDA topic has no words available in c_v dictionary."
                    )
                topic_words.append(words)
            coherence = CoherenceModel(
                topics=topic_words,
                texts=texts,
                dictionary=dictionary,
                coherence="c_v",
                processes=1,
            ).get_coherence()
            if not math.isfinite(float(coherence)):
                raise ValueError("gensim returned a non-finite c_v score.")
            coherence_scores.append(float(coherence))
        return (
            candidates,
            coherence_scores,
            "c_v",
            candidates[
                max(range(len(coherence_scores)), key=coherence_scores.__getitem__)
            ],
        )
    except Exception:
        perplexities = [score for _, _, score in fitted]
        best_index = min(range(len(perplexities)), key=perplexities.__getitem__)
        return candidates, perplexities, "perplexity", candidates[best_index]


def _draw_f09(
    plt: Any,
    frame: pd.DataFrame,
    data_dir: Path,
    out: Path,
    caption: str,
) -> None:
    """Draw LDA coherence c_v or clearly labeled sklearn perplexity fallback."""
    figure, axis = plt.subplots(figsize=(9, 5))
    try:
        ks, values, metric, best_k = _lda_curve(frame, data_dir)
    except (ImportError, OSError, ValueError, json.JSONDecodeError) as exc:
        _placeholder(axis, str(exc))
        figure.suptitle("F09 — LDA coherence/perplexity (không khả dụng)")
        _finish(plt, figure, out / "F09_lda_coherence.png", caption)
        return

    axis.plot(ks, values, marker="o")
    axis.set_xticks(ks)
    axis.set_xlabel("Số chủ đề k")
    if metric == "c_v":
        axis.set_ylabel("Coherence c_v (cao hơn thường tốt hơn)")
        title = "F09 — LDA coherence c_v theo k=3–10 (gensim)"
        best_index = values.index(max(values))
    else:
        axis.set_ylabel("Perplexity sklearn (thấp hơn thường tốt hơn)")
        title = "F09 — LDA perplexity theo k=3–10 (sklearn; không phải c_v)"
        best_index = values.index(min(values))
    axis.scatter([ks[best_index]], [values[best_index]], s=65, zorder=3)
    axis.annotate(
        f"k={best_k}",
        (ks[best_index], values[best_index]),
        xytext=(5, 8),
        textcoords="offset points",
    )
    axis.grid(axis="y", alpha=0.25)
    figure.suptitle(title)
    if metric == "c_v":
        note = (
            "Metric: gensim CoherenceModel(coherence='c_v'); k chọn theo c_v lớn nhất."
        )
    else:
        note = (
            "Metric: sklearn LDA perplexity; đây không phải coherence c_v. "
            "k đánh dấu theo perplexity nhỏ nhất."
        )
    _finish(plt, figure, out / "F09_lda_coherence.png", f"{caption}. {note}")


def _align_rows_to_silver(
    frame: pd.DataFrame,
    matrix: Any,
    doc_ids: list[Any],
) -> Any:
    """Align saved rows to Silver by doc_id and reject stale artifact indexes."""
    if "doc_id" not in frame.columns:
        raise ValueError("Silver is missing `doc_id`; cannot align representations.")
    silver_ids = frame["doc_id"].fillna("").astype(str).tolist()
    ids = [str(item) for item in doc_ids]
    if len(ids) != matrix.shape[0] or len(set(ids)) != len(ids):
        raise ValueError(
            "Representation doc_ids are missing, duplicated, or mismatched."
        )
    if len(silver_ids) != len(ids) or set(silver_ids) != set(ids):
        raise ValueError(
            "Representation index does not match Silver; rerun `fbpipe represent`."
        )
    index_by_id = {doc_id: index for index, doc_id in enumerate(ids)}
    order = [index_by_id[doc_id] for doc_id in silver_ids]
    return matrix[order]


def _embedding_map_data(
    frame: pd.DataFrame,
    data_dir: Path,
) -> tuple[Any, Any, str, str]:
    """Return 2D coordinates and KMeans labels, using E5+UMAP or TF-IDF SVD/PCA."""
    import numpy as np
    from scipy import sparse
    from sklearn.cluster import KMeans
    from sklearn.decomposition import TruncatedSVD

    gold = data_dir / "gold"
    ids_path = gold / "doc_ids.json"
    if not ids_path.is_file():
        raise FileNotFoundError(
            "Missing data/gold/doc_ids.json; run `fbpipe represent`."
        )
    doc_ids = json.loads(ids_path.read_text(encoding="utf-8"))
    if not isinstance(doc_ids, list):
        raise ValueError("data/gold/doc_ids.json must contain a JSON list.")
    e5_path = gold / "e5_embeddings.npy"
    tfidf_path = gold / "tfidf.npz"

    embeddings = None
    fallback_reason = "E5 hoặc umap-learn chưa sẵn có"
    if e5_path.is_file():
        try:
            import umap

            candidate = np.load(e5_path, allow_pickle=False)
            if candidate.ndim != 2:
                raise ValueError("E5 embeddings must be a 2D matrix.")
            embeddings = _align_rows_to_silver(frame, candidate, doc_ids)
            if len(frame) < 3:
                raise ValueError("UMAP needs at least 3 documents for a stable 2D map.")
            cluster_count = min(5, max(2, int(math.sqrt(len(frame)))))
            clusters = KMeans(
                n_clusters=cluster_count,
                random_state=42,
                n_init=10,
            ).fit_predict(embeddings)
            coordinates = umap.UMAP(
                n_components=2,
                n_neighbors=min(15, len(frame) - 1),
                min_dist=0.1,
                metric="cosine",
                random_state=42,
                transform_seed=42,
                n_jobs=1,
            ).fit_transform(embeddings)
            return (
                coordinates,
                clusters,
                "UMAP 2D từ embedding E5, tô màu theo KMeans (seed=42)",
                "E5 + UMAP",
            )
        except Exception as exc:
            fallback_reason = f"E5/UMAP không khả dụng ({type(exc).__name__})"

    if not tfidf_path.is_file():
        raise FileNotFoundError(
            "F11 needs E5+umap-learn or data/gold/tfidf.npz for the fallback."
        )
    tfidf = sparse.load_npz(tfidf_path).tocsr()
    tfidf = _align_rows_to_silver(frame, tfidf, doc_ids)
    if tfidf.shape[0] < 2 or tfidf.shape[1] < 2 or tfidf.nnz == 0:
        raise ValueError("TF-IDF is too small or empty for a 2D embedding map.")

    if tfidf.shape[1] > 2:
        coordinates = TruncatedSVD(n_components=2, random_state=42).fit_transform(tfidf)
        method = "TruncatedSVD 2D từ TF-IDF"
    else:
        from sklearn.decomposition import PCA

        coordinates = PCA(n_components=2, random_state=42).fit_transform(
            tfidf.toarray()
        )
        method = "PCA 2D từ TF-IDF"
    cluster_count = min(5, max(2, int(math.sqrt(len(frame)))))
    clusters = KMeans(
        n_clusters=cluster_count,
        random_state=42,
        n_init=10,
    ).fit_predict(tfidf)
    title = f"{method}, tô màu theo KMeans (fallback: {fallback_reason}; seed=42)"
    return coordinates, clusters, title, method


def _draw_f11(
    plt: Any,
    frame: pd.DataFrame,
    data_dir: Path,
    out: Path,
    caption: str,
) -> None:
    """Draw an embedding map from E5+UMAP or an explicitly labeled TF-IDF fallback."""
    figure, axis = plt.subplots(figsize=(8, 6))
    try:
        coordinates, clusters, title, method = _embedding_map_data(frame, data_dir)
        points = axis.scatter(
            coordinates[:, 0],
            coordinates[:, 1],
            c=clusters,
            cmap="tab10",
            s=36,
            alpha=0.85,
        )
        colorbar = figure.colorbar(points, ax=axis)
        colorbar.set_label("Cụm KMeans")
        axis.set_xlabel(f"{method} — chiều 1")
        axis.set_ylabel(f"{method} — chiều 2")
        axis.grid(alpha=0.2)
        figure.suptitle(f"F11 — {title}")
    except (ImportError, OSError, ValueError, json.JSONDecodeError) as exc:
        _placeholder(axis, str(exc))
        figure.suptitle("F11 — Bản đồ embedding (không khả dụng)")
    _finish(
        plt,
        figure,
        out / "F11_embedding_map.png",
        f"{caption}. Seed=42; màu biểu thị cụm KMeans. UMAP+E5 được ưu tiên; "
        "nếu thiếu thì dùng PCA/TruncatedSVD trên TF-IDF và ghi rõ ở tiêu đề.",
        bottom=0.16,
    )


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _draw_f13(
    plt: Any,
    data_dir: Path,
    out: Path,
    caption: str,
) -> None:
    represent = _read_json(data_dir / "metrics" / "represent.json")
    labels = _read_json(data_dir / "metrics" / "label_eval.json")
    results = labels.get("results", {})
    if not isinstance(results, dict):
        results = {}
    e5 = represent.get("e5", {})
    if not isinstance(e5, dict):
        e5 = {}
    methods = ("bow", "tfidf", "e5")
    names = ("BoW", "TF-IDF", "E5")
    values: list[float | None] = []
    display_names: list[str] = []
    for name, method in zip(names, methods, strict=True):
        result = results.get(method, {})
        if not isinstance(result, dict):
            result = {}
        score = _number(result.get("macro_f1"))
        if method == "e5" and not e5.get("available", False):
            display_names.append(f"{name}\n(không khả dụng)")
            values.append(None)
        else:
            values.append(score)
            dimension_data = represent.get(method, {})
            dimensions = (
                dimension_data.get("dimensions")
                if isinstance(dimension_data, dict)
                else None
            )
            display_names.append(f"{name}\n{dimensions} chiều" if dimensions else name)
    figure, axis = plt.subplots(figsize=(8, 5))
    positions = list(range(len(methods)))
    axis.bar(
        positions,
        [value if value is not None else 0 for value in values],
    )
    for position, value in zip(positions, values, strict=True):
        axis.text(
            position,
            value + 0.025 if value is not None else 0.025,
            f"{value:.3f}" if value is not None else "n/a",
            ha="center",
            va="bottom",
        )
    axis.set_xticks(positions, display_names)
    axis.set_ylabel("Macro-F1")
    axis.set_ylim(0, 1.08)
    axis.grid(axis="y", alpha=0.25)
    proxy_value = labels.get("proxy_labels")
    if proxy_value is True:
        label_caption = "Nhãn đánh giá: proxy_labels=true (nhãn yếu, chỉ chẩn đoán)"
    elif proxy_value is False:
        label_caption = "Nhãn đánh giá: nhãn tay (proxy_labels=false)"
    else:
        label_caption = "Nhãn đánh giá: chưa có metrics (proxy_labels=unknown)"
    figure.suptitle("F13 — So sánh biểu diễn theo Macro-F1")
    _finish(
        plt,
        figure,
        out / "F13_representation_comparison.png",
        f"{caption}. {label_caption}.",
    )


def _metric_seconds(backend: dict[str, Any], key: str) -> float | None:
    bulk = backend.get("bulk_write", {})
    if key == "bulk_write":
        return _number(bulk.get("median_seconds")) if isinstance(bulk, dict) else None
    queries = backend.get("queries", {})
    if not isinstance(queries, dict):
        return None
    aliases = {
        "Q1": ("Q1_keyword_search", "Q1_keyword_scan"),
        "Q2": ("Q2_date_range", "Q2_date_range_scan"),
        "Q3": ("Q3_count_by_month", "Q3_count_by_month_scan"),
    }
    for query_key in aliases.get(key, ()):
        item = queries.get(query_key, {})
        if isinstance(item, dict):
            value = _number(item.get("warm_median_seconds"))
            if value is not None:
                return value
    return None


def _draw_f14(plt: Any, data_dir: Path, out: Path, caption: str) -> None:
    metrics = _read_json(data_dir / "metrics" / "bench_storage.json")
    backends = {
        "SQLite + FTS5": metrics.get("sqlite", {}),
        "Parquet scan": metrics.get("parquet", {}),
    }
    categories = (
        ("bulk_write", "Ghi bulk"),
        ("Q1", "Tìm từ khóa"),
        ("Q2", "Lọc ngày"),
        ("Q3", "Đếm theo tháng"),
    )
    values: dict[str, list[float | None]] = {}
    for name, backend in backends.items():
        source = backend if isinstance(backend, dict) else {}
        values[name] = [_metric_seconds(source, key) for key, _ in categories]
    available = [
        index
        for index in range(len(categories))
        if any(values[name][index] is not None for name in backends)
    ]
    figure, axis = plt.subplots(figsize=(10, 5))
    if not available:
        _placeholder(axis, "Chưa có data/metrics/bench_storage.json hợp lệ.")
    else:
        labels = [categories[index][1] for index in available]
        positions = list(range(len(available)))
        width = 0.36
        for offset, name in enumerate(backends):
            series = [
                values[name][index] if values[name][index] is not None else float("nan")
                for index in available
            ]
            axis.bar(
                [position + (offset - 0.5) * width for position in positions],
                series,
                width,
                label=name,
            )
        axis.set_xticks(positions, labels)
        axis.set_ylabel("Thời gian median (giây; Q1–Q3 dùng warm median)")
        axis.legend()
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("F14 — Benchmark lưu trữ (bản ghi clone từ Silver)")
    _finish(plt, figure, out / "F14_storage_benchmark.png", caption)


def _draw_f15(plt: Any, data_dir: Path, out: Path, caption: str) -> None:
    metrics = _read_json(data_dir / "metrics" / "preprocess.json")
    keys = ("n_raw", "n_after_dedup", "n_after_spam", "n_after_short", "n_kept")
    labels = (
        "Đầu vào",
        "Sau dedup",
        "Sau lọc spam",
        "Sau lọc ngắn",
        "Giữ lại",
    )
    counts = [_number(metrics.get(key)) for key in keys]
    figure, axis = plt.subplots(figsize=(9, 5))
    if not any(value is not None for value in counts):
        _placeholder(axis, "Chưa có data/metrics/preprocess.json hợp lệ.")
    else:
        positions = list(range(len(keys)))
        axis.bar(
            positions,
            [value if value is not None else 0 for value in counts],
        )
        axis.set_xticks(positions, labels, rotation=20, ha="right")
        axis.set_ylabel("Số bản ghi")
        axis.grid(axis="y", alpha=0.25)
        for position, value in zip(positions, counts, strict=True):
            if value is not None:
                axis.text(position, value, f"{int(value)}", ha="center", va="bottom")
    figure.suptitle("F15 — Funnel tiền xử lý")
    _finish(plt, figure, out / "F15_preprocess_funnel.png", caption, bottom=0.2)


def generate_figures(
    *,
    input_path: str | Path = "data/silver/documents.parquet",
    data_dir: str | Path = "data",
    output_dir: str | Path = "docs/figures",
) -> list[Path]:
    """Generate F01/F03/F06/F07/F09/F10/F11/F13/F14/F15 without model downloads."""
    frame = load_silver(input_path)
    plt = _pyplot()
    analysis = analyze_corpus(input_path=input_path, data_dir=data_dir)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    caption = source_caption(frame)
    _draw_f01(plt, frame, destination, caption)
    _draw_f03(plt, analysis, destination, caption)
    _draw_f06(plt, analysis, destination, caption)
    _draw_f07(plt, frame, destination, caption)
    _draw_f09(plt, frame, Path(data_dir), destination, caption)
    _draw_f10(plt, Path(data_dir), destination, caption)
    _draw_f11(plt, frame, Path(data_dir), destination, caption)
    _draw_f13(plt, Path(data_dir), destination, caption)
    _draw_f14(plt, Path(data_dir), destination, caption)
    _draw_f15(plt, Path(data_dir), destination, caption)
    return [destination / name for name in FIGURE_NAMES]
