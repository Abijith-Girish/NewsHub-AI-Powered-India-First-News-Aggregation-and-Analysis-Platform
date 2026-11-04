"""Safe, on-demand extraction of publicly accessible publisher article text.

NewsHub never bypasses paywalls, login walls, CAPTCHAs, robots.txt restrictions,
or other access controls. Full text is kept in the Django cache only; it is not
persisted to the Article model. If a publisher blocks retrieval, callers receive
an explicit limited-content result and can still use the feed description.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import socket
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("newshub.article_extraction")

EXTRACTOR_VERSION = "article-text-v1"
MAX_HTML_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 4
FULL_ARTICLE_WORDS = 120
PARTIAL_ARTICLE_WORDS = 45
JUNK_SELECTORS = (
    "script", "style", "noscript", "svg", "iframe", "form", "button",
    "nav", "footer", "header", "aside", "dialog", "figure", "video",
    "audio", "[aria-hidden='true']", "[hidden]",
)
JUNK_CLASS_MARKERS = (
    "advert", "cookie", "newsletter", "subscribe", "social-share", "share-bar",
    "related-story", "recommended", "comment", "promo", "paywall", "login",
    "site-header", "site-footer", "navigation", "breadcrumb", "toolbar",
)
BOILERPLATE_PHRASES = (
    "subscribe to our newsletter", "sign up for our newsletter",
    "you are receiving this email", "manage your email preferences",
    "unsubscribe from this newsletter", "subscribe to continue reading",
    "subscribe to read the full story", "sign in to continue reading",
    "read more stories", "download the app", "follow us on facebook",
    "follow us on twitter", "follow us on instagram", "advertisement",
    "all rights reserved", "terms of use", "privacy policy",
)
RESTRICTED_MARKERS = (
    "access denied", "verify you are human", "checking your browser",
    "unusual traffic", "enable javascript and cookies to continue",
    "subscribe to continue reading", "subscriber-only content",
    "sign in to read the full article", "you have reached your article limit",
    "this article is for subscribers", "cloudflare ray id",
)


@dataclass(frozen=True)
class ArticleTextResult:
    text: str
    content_status: str
    content_source: str
    method: str
    note: str
    source_url: str
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArticleExtractionError(Exception):
    """Expected extraction failure with a safe, user-displayable reason."""


def clean_article_text(value: str) -> str:
    """Normalize extracted/feed text and remove common non-editorial boilerplate."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\[\s*[\d,]+\s*chars?\s*\]", " ", text, flags=re.I)
    text = re.sub(
        r"Welcome back to TechCrunch(?: Mobility)?[^.!?]*[.!?]?", " ", text, flags=re.I
    )
    paragraphs: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"\n+", text):
        paragraph = re.sub(r"\s+", " ", raw).strip(" \t\u00a0|•")
        if not paragraph:
            continue
        lowered = paragraph.casefold()
        # If feed text or JSON-LD combines a story and a footer in one long
        # paragraph, keep the story text before the first known footer marker.
        for phrase in BOILERPLATE_PHRASES:
            marker_at = lowered.find(phrase)
            if marker_at >= 0:
                paragraph = paragraph[:marker_at].strip()
                lowered = paragraph.casefold()
                break
        if not paragraph:
            continue
        # Drop terse UI fragments, photo credits and link-like calls to action.
        if len(paragraph) < 28 and len(paragraph.split()) < 5:
            continue
        if re.match(r"^(image|photo|file|source)\s*[:\-–]", lowered):
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text or "", flags=re.UNICODE))


def _content_status(text: str) -> str:
    words = _word_count(text)
    if words >= FULL_ARTICLE_WORDS:
        return "full"
    if words >= PARTIAL_ARTICLE_WORDS:
        return "partial"
    return "headline_only"


def _note_for(status: str, reason: str = "") -> str:
    if status == "full":
        return "Full article text was available from the publisher or its feed."
    if status == "partial":
        return "Only part of the article was available. The summary or translation may omit details."
    if reason:
        return reason
    return "Only the headline and short publisher description are available. Open the original article for the full report."


def _make_result(
    text: str,
    *,
    content_source: str,
    method: str,
    source_url: str,
    reason: str = "",
) -> ArticleTextResult:
    cleaned = clean_article_text(text)
    status = _content_status(cleaned)
    return ArticleTextResult(
        text=cleaned,
        content_status=status,
        content_source=content_source,
        method=method,
        note=_note_for(status, reason),
        source_url=source_url,
        word_count=_word_count(cleaned),
    )


def _is_public_http_url(url: str) -> bool:
    """Reject non-web schemes, localhost, private IPs and private DNS targets."""
    try:
        parsed = urlsplit(str(url or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        port = parsed.port
        if port is not None and port not in {80, 443}:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if (
            host in {"localhost", "localhost.localdomain", "example.com", "example.org", "example.net"}
            or host.endswith((".localhost", ".local", ".internal", ".test", ".example.com", ".example.org", ".example.net"))
        ):
            return False
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            try:
                records = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
                addresses = {ipaddress.ip_address(record[4][0]) for record in records}
            except (OSError, socket.gaierror, ValueError):
                return False
        return bool(addresses) and all(address.is_global for address in addresses)
    except (TypeError, ValueError):
        return False


def _robots_allowed(url: str) -> tuple[bool, str]:
    """Respect robots.txt. Unknown/unavailable policies fail closed for extraction."""
    parsed = urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    cache_key = f"newshub:robots:v1:{parsed.scheme}:{parsed.netloc.lower()}"
    cached = cache.get(cache_key)
    if cached is None:
        if not _is_public_http_url(robots_url):
            return False, "The publisher's crawler policy could not be checked safely."
        try:
            response = requests.get(
                robots_url,
                headers={"User-Agent": settings.NEWSHUB.get("USER_AGENT", "NewsHub/1.0")},
                timeout=(2.5, 3.5),
                allow_redirects=False,
            )
        except requests.RequestException:
            return False, "The publisher's crawler policy could not be checked; extraction was skipped."
        if response.status_code in {404, 410}:
            cached = {"kind": "missing"}
        elif response.status_code == 200:
            robots_text = response.text[:512 * 1024]
            lowered = robots_text.lower()
            if any(marker in lowered for marker in ("verify you are human", "access denied", "cloudflare ray id")):
                return False, "The publisher's crawler policy could not be verified; extraction was skipped."
            cached = {"kind": "rules", "lines": robots_text.splitlines()[:10000]}
        elif response.status_code in {401, 403}:
            cached = {"kind": "blocked"}
        else:
            return False, "The publisher's crawler policy was unavailable; extraction was skipped."
        cache.set(cache_key, cached, 60 * 60 * 12)

    if cached.get("kind") == "blocked":
        return False, "The publisher does not permit automated page retrieval."
    if cached.get("kind") == "missing":
        return True, ""
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(cached.get("lines") or [])
    user_agent = settings.NEWSHUB.get("USER_AGENT", "NewsHub/1.0")
    if not parser.can_fetch(user_agent, url):
        return False, "The publisher's robots.txt disallows automated retrieval of this page."
    return True, ""


def _download_html(url: str) -> tuple[str, str]:
    """Download a bounded HTML document while validating every redirect target."""
    current_url = url
    timeout = max(2.0, min(float(settings.NEWSHUB.get("ARTICLE_EXTRACTION_TIMEOUT", 9)), 20.0))
    max_bytes = max(256 * 1024, min(
        int(settings.NEWSHUB.get("ARTICLE_EXTRACTION_MAX_BYTES", MAX_HTML_BYTES)),
        5 * 1024 * 1024,
    ))
    headers = {
        "User-Agent": settings.NEWSHUB.get("USER_AGENT", "NewsHub/1.0 (educational news aggregator)"),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    }
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_public_http_url(current_url):
            raise ArticleExtractionError("The publisher URL or redirect was not a public web address.")
        if settings.NEWSHUB.get("ARTICLE_EXTRACTION_RESPECT_ROBOTS", True):
            allowed, policy_reason = _robots_allowed(current_url)
            if not allowed:
                raise ArticleExtractionError(policy_reason)
        try:
            response = requests.get(
                current_url,
                headers=headers,
                timeout=(min(4.0, timeout), timeout),
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout as exc:
            raise ArticleExtractionError("The publisher page timed out. The original article link is still available.") from exc
        except requests.RequestException as exc:
            raise ArticleExtractionError("The publisher page could not be reached. The original article link is still available.") from exc

        try:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise ArticleExtractionError("The publisher returned an invalid redirect.")
                current_url = urljoin(current_url, location)
                continue
            if response.status_code in {401, 402, 403, 407, 429, 451}:
                raise ArticleExtractionError(
                    "The publisher restricted automated access. NewsHub will not bypass that restriction."
                )
            if response.status_code != 200:
                raise ArticleExtractionError(f"The publisher page returned HTTP {response.status_code}.")
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if content_type and not any(kind in content_type for kind in ("text/html", "application/xhtml+xml")):
                raise ArticleExtractionError("The publisher URL did not return an HTML article page.")
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                raise ArticleExtractionError("The publisher page is larger than the extraction size limit.")
            body = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ArticleExtractionError("The publisher page exceeded the extraction size limit.")
            if not body:
                raise ArticleExtractionError("The publisher page returned an empty response.")
            encoding = response.encoding or "utf-8"
            try:
                html_text = body.decode(encoding, errors="replace")
            except LookupError:
                html_text = body.decode("utf-8", errors="replace")
            return html_text, current_url
        finally:
            response.close()
    raise ArticleExtractionError("The publisher redirected too many times; extraction was stopped.")


def _iter_jsonld_article_bodies(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _iter_jsonld_article_bodies(item)
    elif isinstance(value, dict):
        body = value.get("articleBody")
        kind = value.get("@type", "")
        kinds = kind if isinstance(kind, list) else [kind]
        if body and any("article" in str(item).lower() for item in kinds):
            yield str(body)
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _iter_jsonld_article_bodies(child)


def _extract_with_trafilatura(html_text: str, url: str) -> str:
    try:
        import trafilatura
    except ImportError:
        return ""
    for precision in (True, False):
        try:
            extracted = trafilatura.extract(
                html_text,
                url=url,
                include_comments=False,
                include_tables=False,
                favor_precision=precision,
                output_format="txt",
            )
        except Exception as exc:  # library-specific parse errors must not break the request
            logger.debug("Trafilatura extraction attempt failed: %s", exc.__class__.__name__)
            continue
        cleaned = clean_article_text(extracted or "")
        if _word_count(cleaned) >= PARTIAL_ARTICLE_WORDS:
            return cleaned
    return ""


def _extract_with_beautifulsoup(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    candidates: list[str] = []
    # Read JSON-LD before scripts are removed as part of boilerplate cleaning.
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
            candidates.extend(_iter_jsonld_article_bodies(payload))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    for tag in soup.select(",".join(JUNK_SELECTORS)):
        tag.decompose()
    for node in list(soup.find_all(True)):
        attrs = " ".join([
            str(node.get("id") or ""),
            " ".join(str(item) for item in (node.get("class") or [])),
        ]).lower()
        if any(marker in attrs for marker in JUNK_CLASS_MARKERS):
            node.decompose()

    selectors = (
        '[itemprop="articleBody"]', "article", "main",
        '[class*="article-body"]', '[class*="articleBody"]',
        '[class*="story-body"]', '[class*="storyBody"]',
        '[class*="article-content"]', '[class*="articleContent"]',
        '[class*="story-content"]',
    )
    for selector in selectors:
        for node in soup.select(selector)[:4]:
            paragraphs = [p.get_text(" ", strip=True) for p in node.select("p, h2, h3, li")]
            if not paragraphs:
                paragraphs = [node.get_text("\n", strip=True)]
            candidates.append("\n\n".join(paragraphs))

    all_paragraphs = []
    for paragraph in soup.select("p"):
        if paragraph.find_parent(["nav", "footer", "header", "aside", "form"]):
            continue
        link_text = paragraph.get_text(" ", strip=True)
        total_len = max(len(link_text), 1)
        linked_len = sum(len(anchor.get_text(" ", strip=True)) for anchor in paragraph.select("a"))
        if linked_len / total_len > 0.55:
            continue
        all_paragraphs.append(link_text)
    if all_paragraphs:
        candidates.append("\n\n".join(all_paragraphs))

    cleaned_candidates = [clean_article_text(candidate) for candidate in candidates]
    cleaned_candidates = [item for item in cleaned_candidates if _word_count(item) >= PARTIAL_ARTICLE_WORDS]
    if not cleaned_candidates:
        return ""
    # Prefer a substantive candidate without allowing unlimited page boilerplate.
    return max(cleaned_candidates, key=lambda item: min(_word_count(item), 5000))


def _page_is_restricted(html_text: str, extracted_text: str) -> bool:
    if _word_count(extracted_text) >= PARTIAL_ARTICLE_WORDS * 2:
        return False
    probe = BeautifulSoup(html_text[:500000], "html.parser").get_text(" ", strip=True).lower()
    return any(marker in probe for marker in RESTRICTED_MARKERS)


def _extract_html(html_text: str, url: str, expected_title: str = "") -> tuple[str, str]:
    soup = BeautifulSoup(html_text, "html.parser")
    page_title = soup.select_one('meta[property="og:title"]') or soup.select_one('meta[name="twitter:title"]')
    title = (page_title.get("content", "") if page_title else "") or (soup.title.get_text(" ", strip=True) if soup.title else "")
    if expected_title and title:
        stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "after", "with", "by", "from"}
        expected_tokens = {
            token for token in re.findall(r"[a-z0-9]+", expected_title.casefold())
            if len(token) > 2 and token not in stopwords
        }
        page_tokens = {
            token for token in re.findall(r"[a-z0-9]+", title.casefold())
            if len(token) > 2 and token not in stopwords
        }
        # Require at least two meaningful shared tokens (or one for very short
        # headlines) so a generic homepage/section page is not mistaken for this story.
        minimum_overlap = 2 if len(expected_tokens) >= 4 else 1
        if expected_tokens and page_tokens and len(expected_tokens & page_tokens) < minimum_overlap:
            raise ArticleExtractionError(
                "The publisher page title does not match this stored headline; unrelated text was not used."
            )
    extracted = _extract_with_trafilatura(html_text, url)
    method = "trafilatura"
    if _word_count(extracted) < PARTIAL_ARTICLE_WORDS:
        extracted = _extract_with_beautifulsoup(html_text)
        method = "beautifulsoup_fallback"
    extracted = clean_article_text(extracted)
    if _page_is_restricted(html_text, extracted):
        raise ArticleExtractionError("The publisher returned a restricted page rather than readable article text.")
    if _word_count(extracted) < PARTIAL_ARTICLE_WORDS:
        raise ArticleExtractionError("The page did not expose enough article text to make a reliable summary.")
    # Avoid returning title-only or generic landing pages as article bodies.
    if title and extracted.strip().casefold() == title.strip().casefold():
        raise ArticleExtractionError("The publisher page contained only a headline, not article text.")
    return extracted[:50000], method


def _inline_result(article) -> ArticleTextResult:
    content = clean_article_text(article.content or "")
    description = clean_article_text(article.description or "")
    if content and description and description.casefold() not in content.casefold():
        text = f"{content}\n\n{description}"
        source = "publisher_feed"
    elif content:
        text, source = content, "publisher_feed"
    elif description:
        text, source = description, "description"
    else:
        text, source = article.title or "", "title"
    return _make_result(
        text,
        content_source=source,
        method="feed_content" if source == "publisher_feed" else source,
        source_url=article.source_url or "",
    )


def extract_article_content(article, *, force: bool = False) -> ArticleTextResult:
    """Return best available article text, fetching public publisher text on demand.

    The function is intentionally fail-soft: publisher, robots, network or parser
    failures do not break the article reader. It always returns the best text already
    present in the feed, together with a status explaining its completeness.
    """
    inline = _inline_result(article)
    if inline.content_status == "full" and not force:
        return inline

    url = str(article.source_url or "").strip()
    if not url:
        return inline

    config = settings.NEWSHUB
    if not config.get("ARTICLE_EXTRACTION_ENABLED", True):
        return ArticleTextResult(
            **{
                **inline.to_dict(),
                "note": _note_for(inline.content_status, "Publisher-page extraction is disabled; only feed text is available."),
            }
        )

    fingerprint = hashlib.sha256(
        f"{url}|{article.title}|{inline.text}".encode("utf-8", errors="ignore")
    ).hexdigest()[:24]
    cache_key = f"newshub:article-text:{EXTRACTOR_VERSION}:{fingerprint}"
    if not force:
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            try:
                cached_result = ArticleTextResult(**cached)
                if cached_result.word_count >= inline.word_count:
                    return cached_result
            except (TypeError, ValueError):
                cache.delete(cache_key)

    result: ArticleTextResult | None = None
    try:
        if not _is_public_http_url(url):
            raise ArticleExtractionError("The publisher URL is not a safe public HTTP(S) address.")
        html_text, final_url = _download_html(url)
        extracted_text, method = _extract_html(html_text, final_url, article.title)
        result = _make_result(
            extracted_text,
            content_source="publisher_page",
            method=method,
            source_url=final_url,
        )
    except ArticleExtractionError as exc:
        reason = str(exc)
        logger.info("Article extraction unavailable: article_id=%s host=%s reason=%s", article.pk, urlsplit(url).hostname or "unknown", reason)
    except Exception as exc:  # noqa: BLE001 - never break reader or summarizer on parser bugs
        reason = "The publisher page could not be processed safely. The original article link remains available."
        logger.warning(
            "Unexpected article extraction failure: article_id=%s error=%s",
            article.pk, exc.__class__.__name__,
        )

    if result and result.word_count > inline.word_count:
        cache.set(cache_key, result.to_dict(), int(config.get("ARTICLE_EXTRACTION_CACHE_TTL", 21600)))
        return result

    # Keep a short negative cache to avoid repeatedly requesting a blocked/empty page.
    fallback = ArticleTextResult(
        **{
            **inline.to_dict(),
            "note": _note_for(inline.content_status, reason if "reason" in locals() else "The publisher page did not provide more article text."),
        }
    )
    cache.set(cache_key, fallback.to_dict(), int(config.get("ARTICLE_EXTRACTION_FAILURE_TTL", 600)))
    return fallback
