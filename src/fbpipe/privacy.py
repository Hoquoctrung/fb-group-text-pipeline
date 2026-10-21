"""Privacy-preserving transformations for imported and collected text."""

from __future__ import annotations

import hashlib
import hmac
import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"https?://[^\s<]+|www\.[^\s<]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+84|0084|0)\d(?:[\s.\-]?\d){8,10}(?!\d)")


def hash_author(author_id: str, salt: str) -> str:
    """Return a deterministic HMAC-SHA256 pseudonym for an author identifier."""
    if not author_id:
        raise ValueError("author_id must not be empty")
    if not salt:
        raise ValueError("FBPIPE_SALT must not be empty")
    return hmac.new(
        salt.encode("utf-8"), author_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def scrub_pii(text: str) -> str:
    """Replace common URL, email, and Vietnamese phone-number patterns."""
    text = URL_RE.sub("<URL>", text)
    text = EMAIL_RE.sub("<EMAIL>", text)
    return PHONE_RE.sub("<PHONE>", text)
