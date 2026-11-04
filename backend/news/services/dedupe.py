"""URL/title normalization and duplicate detection helpers."""
from __future__ import annotations

import hashlib
import html
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_cid", "utm_reader", "utm_referrer",
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "ref", "ref_src", "ref_url", "source", "cmpid", "ito", "smid",
}

_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been", "it",
    "its", "this", "that", "these", "those", "after", "before", "over", "under",
    "new", "says", "say", "said", "amid", "about", "into", "than", "then",
}


def normalize_url(url: str) -> str:
    """Return a canonical URL used only for duplicate detection."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_PARAMS
    ]
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (parsed.scheme.lower(), netloc, path, "", urlencode(query), "")
    )


def is_valid_article_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_text(value: str, limit: int | None = None) -> str:
    if not value:
        return ""
    text = html.unescape(str(value))
    text = _WHITESPACE.sub(" ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def clean_title(title: str, source_name: str = "") -> str:
    """Remove a trailing publisher suffix only when it matches the known source.

    Google News appends ' - Publisher'; stripping only the exact known suffix
    avoids mangling genuine headlines that contain a dash.
    """
    text = clean_text(title)
    if not text:
        return ""
    if source_name:
        for separator in (" - ", " | ", " — ", " – "):
            suffix = f"{separator}{source_name}"
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break
    return text


def title_fingerprint(title: str) -> str:
    normalized = _NON_ALNUM.sub(" ", title.lower())
    tokens = [token for token in normalized.split() if token not in _STOPWORDS]
    return " ".join(tokens)


def title_tokens(title: str) -> set[str]:
    return {token for token in title_fingerprint(title).split() if len(token) > 2}


def build_dedupe_key(url: str, title: str) -> str:
    """Stable key for a URL, falling back to the headline when no URL exists."""
    canonical = normalize_url(url)
    basis = canonical or title_fingerprint(title) or title.strip().lower()
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def is_near_duplicate(title: str, other_title: str, threshold: float = 0.82) -> bool:
    """Catch syndicated copies of the same headline from different URLs."""
    left, right = title_tokens(title), title_tokens(other_title)
    if not left or not right:
        return False
    overlap = len(left & right) / len(left | right)
    if overlap >= threshold:
        return True
    if abs(len(left) - len(right)) <= 4:
        return SequenceMatcher(None, " ".join(sorted(left)), " ".join(sorted(right))).ratio() >= 0.9
    return False
