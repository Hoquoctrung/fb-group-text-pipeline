"""Pure, independently testable S0-S11 text preprocessing transforms."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

Doc = dict[str, Any]
TransformFunction = Callable[[Doc], Doc]

_URL_RE = re.compile(r"https?://[^\s<>]+|www\.[^\s<>]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+84|0084|0)(?:[ .-]?\d){8,10}(?!\w)")
_MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_.]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#([\w]+)", re.UNICODE)
_TOKEN_RE = re.compile(
    r"<[a-z_]+>|[^\W\d_]+(?:[_'’][^\W\d_]+)*|\d+(?:[.,]\d+)*",
    re.IGNORECASE | re.UNICODE,
)
_EMOJI_BASE_RE = re.compile(
    "[\\U0001F1E6-\\U0001F1FF\\U0001F300-\\U0001FAFF\\U00002600-\\U000027BF]"
)
_EMOJI_FORMAT_RE = re.compile(r"[\uFE0F\u200D\u20E3]")
_SPAM_WORD_RE = re.compile(r"\b(?:inbox|zalo|sale|liên\s+hệ|giá\s+rẻ)\b", re.I)
_UI_EXACT = {
    "xem thêm",
    "see more",
    "đã chỉnh sửa",
    "edited",
    "thích · phản hồi",
    "like · reply",
    "thích",
    "phản hồi",
    "comment",
    "reply",
}
_UI_TRAILING_RE = re.compile(r"\s+(?:xem thêm|see more|đã chỉnh sửa|edited)\s*$", re.I)


@dataclass(frozen=True)
class Transform:
    """A named deterministic transform that returns a new document mapping."""

    name: str
    _function: TransformFunction

    def apply(self, doc: Doc) -> Doc:
        """Apply this transform without mutating the input mapping."""
        updated = self._function(dict(doc))
        return updated


def _read_word_file(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _read_teencode(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not path.exists():
        return mapping
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t", maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            mapping[parts[0].strip().casefold()] = parts[1].strip()
    return mapping


def _load_english_stopwords() -> set[str]:
    fallback = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "here",
        "hers",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "ours",
        "she",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "too",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    }
    try:
        from nltk.corpus import stopwords

        return {word.casefold() for word in stopwords.words("english")}
    except (ImportError, LookupError):
        return fallback


def load_english_reference_words() -> set[str] | None:
    """Load NLTK's English reference vocabulary without downloading corpora."""
    try:
        from nltk.corpus import words

        return {word.casefold() for word in words.words()}
    except (ImportError, LookupError):
        return None


def _diacritic_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    accented = 0
    for char in letters:
        if char.casefold() == "đ":
            accented += 1
            continue
        if any(
            unicodedata.category(mark) == "Mn"
            for mark in unicodedata.normalize("NFD", char)
        ):
            accented += 1
    return accented / len(letters)


@lru_cache(maxsize=1)
def _lingua_detector() -> tuple[Any, Any, Any] | None:
    try:
        from lingua import Language, LanguageDetectorBuilder

        detector = LanguageDetectorBuilder.from_languages(
            Language.VIETNAMESE,
            Language.ENGLISH,
        ).build()
        return detector, Language.VIETNAMESE, Language.ENGLISH
    except ImportError:
        return None


def _detect_language(text: str, ratio: float) -> str:
    letters = sum(char.isalpha() for char in text)
    if letters < 4:
        return "unknown"
    if ratio >= 0.015:
        return "vi"
    language_bundle = _lingua_detector()
    if language_bundle is not None:
        detector, vietnamese, english = language_bundle
        try:
            detected = detector.detect_language_of(text)
        except (ValueError, RuntimeError):
            detected = None
        if detected == vietnamese:
            return "vi"
        if detected == english:
            return "en"
    return "en" if re.search(r"[A-Za-z]{2,}", text) else "unknown"


def _normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(
        str.maketrans(
            {
                "“": '"',
                "”": '"',
                "„": '"',
                "‘": "'",
                "’": "'",
                "‛": "'",
                "–": "-",
                "—": "-",
            }
        )
    )
    cleaned: list[str] = []
    for char in text:
        category = unicodedata.category(char)
        if char.isspace():
            cleaned.append(" ")
        elif category in {"Cc", "Cf", "Cs"}:
            continue
        else:
            cleaned.append(char)
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()


def _remove_ui_noise(text: str) -> str:
    output_lines: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        if candidate.casefold() in _UI_EXACT:
            continue
        cleaned = _UI_TRAILING_RE.sub("", line)
        cleaned = re.sub(
            r"\s+(?:thích\s*[·•]\s*phản hồi|like\s*[·•]\s*reply)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        output_lines.append(cleaned)
    return re.sub(r"\s+", " ", " ".join(output_lines)).strip()


def _demojize_and_remove(text: str) -> tuple[str, str, int]:
    try:
        import emoji

        emoji_count = len(emoji.emoji_list(text))
        demojized = emoji.demojize(text, language="en")
        clean_text = emoji.replace_emoji(text, replace="")
        return clean_text, demojized, emoji_count
    except ImportError:
        emoji_count = len(_EMOJI_BASE_RE.findall(text))
        clean_text = _EMOJI_BASE_RE.sub("", text)
        clean_text = _EMOJI_FORMAT_RE.sub("", clean_text)
        # Keep the original Unicode string when the optional demojizer is absent.
        return clean_text, text, emoji_count


def _collapse_repeats(text: str, max_repeats: int) -> tuple[str, int]:
    letter_pattern = re.compile(r"([^\W\d_])\1{2,}", re.IGNORECASE | re.UNICODE)
    punctuation_pattern = re.compile(r"([!?.,])\1{1,}")
    counter = 0

    def replace_letters(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        return match.group(1) * max_repeats

    def replace_punctuation(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        return match.group(1)

    text = letter_pattern.sub(replace_letters, text)
    text = punctuation_pattern.sub(replace_punctuation, text)
    return text, counter


def _expand_teencode(
    text: str,
    mapping: dict[str, str],
    ambiguous: set[str],
) -> tuple[str, int]:
    hits = 0
    output = text
    for short, expanded in mapping.items():
        if short in ambiguous:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(short)}(?!\w)", re.IGNORECASE)

        def replacement(
            match: re.Match[str],
            expanded: str = expanded,
        ) -> str:
            nonlocal hits
            hits += 1
            return expanded

        output = pattern.sub(replacement, output)

    # Context-sensitive terms: preserve 5k; map standalone 'k' and 'r'.
    k_pattern = re.compile(r"(?<!\w)k(?!\w)", re.IGNORECASE)

    def replace_k(match: re.Match[str]) -> str:
        nonlocal hits
        preceding = output[: match.start()].rstrip()
        if preceding and preceding[-1].isdigit():
            return match.group(0)
        hits += 1
        return "không"

    output = k_pattern.sub(replace_k, output)
    r_pattern = re.compile(r"(?<!\w)r(?!\w)", re.IGNORECASE)

    def replace_r(match: re.Match[str]) -> str:
        nonlocal hits
        hits += 1
        return "rồi"

    output = r_pattern.sub(replace_r, output)
    return output, hits


def _tokenize(text: str) -> list[str]:
    for module_name in (
        "underthesea",
        "pyvi.ViTokenizer",
    ):
        try:
            if module_name == "underthesea":
                from underthesea import word_tokenize

                segmented = word_tokenize(text, format="text")
                if isinstance(segmented, list):
                    segmented = " ".join(segmented)
            else:
                from pyvi import ViTokenizer

                segmented = ViTokenizer.tokenize(text)
            return _TOKEN_RE.findall(segmented.casefold())
        except (ImportError, LookupError, RuntimeError, ValueError):
            continue
    return _TOKEN_RE.findall(text.casefold())


def _morphology(
    tokens: list[str],
    english_words: set[str] | None,
    vietnamese_unaccented: set[str],
) -> tuple[list[str], list[str]]:
    stems = list(tokens)
    lemmas = list(tokens)
    if not english_words:
        return stems, lemmas
    try:
        from nltk.stem import SnowballStemmer, WordNetLemmatizer

        stemmer = SnowballStemmer("english")
        lemmatizer = WordNetLemmatizer()
    except ImportError:
        return stems, lemmas

    eligible: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        lowered = token.casefold()
        if (
            re.fullmatch(r"[A-Za-z]+", token)
            and len(token) >= 3
            and lowered in english_words
            and lowered not in vietnamese_unaccented
        ):
            eligible.append((index, lowered))
    pos_by_index: dict[int, str] = {}
    try:
        from nltk import pos_tag

        tagged = pos_tag([token for _, token in eligible])
        for (index, _), (_, pos) in zip(eligible, tagged, strict=False):
            pos_by_index[index] = _wordnet_pos(pos)
    except (ImportError, LookupError):
        pos_by_index = {}

    for index, token in eligible:
        stems[index] = stemmer.stem(token)
        try:
            lemma_pos = pos_by_index.get(index, "n")
            lemmas[index] = lemmatizer.lemmatize(token, pos=lemma_pos)
        except LookupError:
            lemmas[index] = token
    return stems, lemmas


def _wordnet_pos(pos_tag: str) -> str:
    if pos_tag.startswith("J"):
        return "a"
    if pos_tag.startswith("V"):
        return "v"
    if pos_tag.startswith("R"):
        return "r"
    return "n"


def _spam_features(doc: Doc) -> tuple[float, bool, float]:
    text = str(doc.get("text_raw", ""))
    clean_text = str(doc.get("text_clean", ""))
    score = 0.0
    if "<phone>" in clean_text.casefold():
        score += 1.0
    score += min(2.0, len(_SPAM_WORD_RE.findall(text)) * 0.8)
    if int(doc.get("n_url", 0)) > 0:
        score += min(1.5, int(doc.get("n_url", 0)) * 0.75)
    letters = [char for char in text if char.isalpha()]
    uppercase_ratio = (
        sum(char.isupper() for char in letters) / len(letters) if letters else 0.0
    )
    if len(letters) >= 8 and uppercase_ratio >= 0.45:
        score += 1.0
    if int(doc.get("n_repeated_runs", 0)) > 0:
        score += 0.5
    return round(score, 3), score >= 2.0, uppercase_ratio


def _strip_token(token: str) -> str:
    return token.casefold().strip()


def build_transforms(
    resource_dir: str | Path = "resources",
    *,
    collapse_repeats_to: int = 2,
    min_tokens: int = 3,
    english_words: set[str] | None = None,
    load_english_reference: bool = True,
) -> tuple[list[Transform], dict[str, Any]]:
    """Build S0-S11 transforms and return runtime resource metadata.

    Optional NLP corpora are never downloaded automatically. Missing optional
    packages/corpora trigger deterministic fallbacks and are reported in metrics.
    """
    resources = Path(resource_dir)
    teencode = _read_teencode(resources / "vi_teencode.tsv")
    vi_stopwords = _read_word_file(resources / "vi_stopwords.txt")
    vi_ambiguous = _read_word_file(resources / "vi_ambiguous.txt")
    en_extra_stopwords = _read_word_file(resources / "en_extra_stopwords.txt")
    domain_stopwords = _read_word_file(resources / "domain_stopwords.txt")
    english_stopwords = _load_english_stopwords() | en_extra_stopwords
    if english_words is None and load_english_reference:
        english_words = load_english_reference_words()
    if english_words is not None:
        english_words = {word.casefold() for word in english_words}

    vietnamese_unaccented: set[str] = set()
    for word in vi_stopwords | set(teencode.values()) | set(teencode):
        decomposed = unicodedata.normalize("NFD", word.casefold())
        vietnamese_unaccented.add(
            "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
        )
    vietnamese_unaccented.update(
        {
            "khong",
            "duoc",
            "nguoi",
            "sinh",
            "vien",
            "hoc",
            "tap",
            "chua",
            "dang",
            "cua",
            "va",
            "la",
            "ban",
            "minh",
            "mot",
            "nhieu",
            "voi",
        }
    )

    def s0(doc: Doc) -> Doc:
        text = str(doc.get("text_raw", doc.get("text_clean", "")))
        ratio = _diacritic_ratio(text)
        doc["has_diacritics_ratio"] = round(ratio, 6)
        doc["lang"] = _detect_language(text, ratio)
        return doc

    def s1(doc: Doc) -> Doc:
        raw = str(doc.get("text_raw", doc.get("text_clean", "")))
        doc["text_normalized"] = _normalize_unicode(raw)
        doc["text_clean"] = doc["text_normalized"]
        return doc

    def s2(doc: Doc) -> Doc:
        text = str(doc.get("text_clean", ""))
        doc["text_clean"] = _remove_ui_noise(text)
        return doc

    def s3(doc: Doc) -> Doc:
        text = str(doc.get("text_clean", ""))
        urls = _URL_RE.findall(text)
        emails = _EMAIL_RE.findall(text)
        phones = _PHONE_RE.findall(text)
        mentions = _MENTION_RE.findall(text)
        hashtags = _HASHTAG_RE.findall(text)
        text = _URL_RE.sub(" <URL> ", text)
        text = _EMAIL_RE.sub(" <EMAIL> ", text)
        text = _PHONE_RE.sub(" <PHONE> ", text)
        text = _MENTION_RE.sub(" <USER> ", text)
        text = _HASHTAG_RE.sub(lambda match: f" {match.group(1)} ", text)
        doc["text_clean"] = re.sub(r"\s+", " ", text).strip()
        doc["n_url"] = len(urls)
        doc["n_email"] = len(emails)
        doc["n_phone"] = len(phones)
        doc["n_mention"] = len(mentions)
        doc["hashtags"] = hashtags
        doc["n_hashtag"] = len(hashtags)
        return doc

    def s4(doc: Doc) -> Doc:
        text = str(doc.get("text_clean", ""))
        clean_text, demojized, count = _demojize_and_remove(text)
        doc["text_clean"] = re.sub(r"\s+", " ", clean_text).strip()
        doc["text_demojized"] = demojized
        doc["n_emoji"] = count
        return doc

    def s5(doc: Doc) -> Doc:
        text = str(doc.get("text_clean", ""))
        cleaned, repeated_runs = _collapse_repeats(text, collapse_repeats_to)
        doc["text_clean"] = re.sub(r"\s+", " ", cleaned).strip()
        doc["n_repeated_runs"] = repeated_runs
        return doc

    def s6(doc: Doc) -> Doc:
        text = str(doc.get("text_clean", ""))
        expanded, hits = _expand_teencode(text, teencode, vi_ambiguous)
        doc["text_clean"] = re.sub(r"\s+", " ", expanded).strip()
        doc["teencode_hits"] = hits
        return doc

    def s7(doc: Doc) -> Doc:
        cased = str(doc.get("text_clean", ""))
        doc["text_cased"] = cased
        doc["text_clean"] = cased.casefold()
        return doc

    def s8(doc: Doc) -> Doc:
        tokens = _tokenize(str(doc.get("text_clean", "")))
        doc["tokens"] = tokens
        doc["n_tokens"] = len(tokens)
        return doc

    def s9(doc: Doc) -> Doc:
        tokens = [_strip_token(token) for token in doc.get("tokens", [])]
        stopwords = vi_stopwords | english_stopwords | domain_stopwords
        placeholders = {"<url>", "<email>", "<phone>", "<user>"}
        doc["tokens_nostop"] = [
            token
            for token in tokens
            if token not in stopwords and token not in placeholders
        ]
        return doc

    def s10(doc: Doc) -> Doc:
        tokens = list(doc.get("tokens_nostop", doc.get("tokens", [])))
        stems, lemmas = _morphology(tokens, english_words, vietnamese_unaccented)
        doc["stems"] = stems
        doc["lemmas"] = lemmas
        doc["english_morphology_available"] = english_words is not None
        return doc

    def s11(doc: Doc) -> Doc:
        token_count = int(doc.get("n_tokens", len(doc.get("tokens", []))))
        doc["is_short"] = token_count < min_tokens
        spam_score, is_spam, uppercase_ratio = _spam_features(doc)
        doc["spam_score"] = spam_score
        doc["is_spam"] = is_spam
        doc["uppercase_ratio"] = round(uppercase_ratio, 6)
        doc["is_duplicate"] = False
        doc["dup_group"] = None
        doc["keep"] = not (doc["is_short"] or doc["is_spam"])
        return doc

    transforms = [
        Transform("S0_language_detection", s0),
        Transform("S1_unicode_normalization", s1),
        Transform("S2_ui_noise_removal", s2),
        Transform("S3_pii_entities", s3),
        Transform("S4_emoji", s4),
        Transform("S5_repeat_collapse", s5),
        Transform("S6_teencode", s6),
        Transform("S7_lowercase", s7),
        Transform("S8_tokenization", s8),
        Transform("S9_stopwords", s9),
        Transform("S10_english_morphology", s10),
        Transform("S11_quality_flags", s11),
    ]
    metadata = {
        "resource_dir": str(resources),
        "teencode_entries": len(teencode),
        "vietnamese_stopwords": len(vi_stopwords),
        "english_stopwords_source": (
            "NLTK corpus when available; otherwise built-in fallback"
        ),
        "english_reference_vocabulary_available": english_words is not None,
        "english_morphology_enabled": english_words is not None,
        "dedup_threshold": 0.85,
        "dedup_shingle_size": 3,
    }
    return transforms, metadata


def tokenize_for_ablation(text: str) -> list[str]:
    """Use the deterministic regex tokenizer for ablation baselines."""
    return _TOKEN_RE.findall(text.casefold())
