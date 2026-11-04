"""Evidence-based claim analysis.

How it works (and what it does not do):
1. Extract the claim text.
2. Search independent news coverage / fact-check reporting for related items.
3. Score each retrieved item for relevance and for explicit supporting or
   contradicting language (lexical cues + word overlap).
4. Produce one of four conservative labels, or "insufficient evidence".
5. Store every evidence link that contributed to the assessment.

This is an informational prototype, not a verified fact-checking service. An
absence of contradictions is never treated as proof, and a machine prediction is
never presented as truth. When an LLM is configured it only *explains* the
rule-derived result using the retrieved evidence; it cannot change the verdict.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from news.models import Article, FactCheck
from news.ml.story_matching import find_claim_matches
from news.providers import search_external
from news.providers.base import NormalizedArticle
from news.services.dedupe import clean_text, normalize_url
from news.services.llm import chat_completion, is_llm_enabled

logger = logging.getLogger("newshub.factcheck")

# A transparent, deliberately modest allowlist of established publishers and
# fact-checking organisations. It is a heuristic for *corroboration*, not an
# oracle: evidence from other sites is still shown to the user, but it cannot
# on its own move a verdict to supported/contradicted. This is what prevents
# conspiracy sites echoing a false claim from producing a "supported" label.
ESTABLISHED_SOURCES = {
    "reuters",
    "associated press",
    "ap news",
    "ap fact check",
    "bbc news",
    "bbc",
    "the guardian",
    "guardian",
    "npr",
    "the new york times",
    "new york times",
    "the washington post",
    "washington post",
    "cnn",
    "cnbc",
    "bloomberg",
    "financial times",
    "the wall street journal",
    "wall street journal",
    "espn",
    "nature",
    "science",
    "stat news",
    "al jazeera",
    "snopes",
    "politifact",
    "factcheck.org",
    "full fact",
    "afp fact check",
    "usa today",
    "the verge",
    "ars technica",
    "techcrunch",
    "wired",
    "mit technology review",
    "the hollywood reporter",
    "variety",
    "education week",
    "inside higher ed",
    "un news",
    "world health organization",
    "nasa",
    "noaa",
    "pbs",
    "abc news",
    "cbs news",
    "nbc news",
    "axios",
    "politico",
    "the atlantic",
    "the economist",
    "forbes",
    "fortune",
    "business insider",
    "sky news",
    "france 24",
    "deutsche welle",
    "cbc",
    "the sydney morning herald",
    "south china morning post",
    "the times of india",
    "times of india",
    "the hindu",
    "the indian express",
    "indian express",
    "ndtv",
    "wion",
    "hindustan times",
    "india today",
    "the economic times",
    "economic times",
    "mint",
    "business standard",
    "press trust of india",
    "pti",
    "news18",
    "firstpost",
    "the print",
    "scroll.in",
    "the wire",
    "boom live",
    "alt news",
    "factly",
    "newschecker",
    "vishvas news",
    "pib fact check",
    "afp",
    "the telegraph",
}

FACT_CHECK_SOURCES = {
    "snopes",
    "politifact",
    "factcheck.org",
    "full fact",
    "afp fact check",
    "ap fact check",
    "boom live",
    "alt news",
    "factly",
    "newschecker",
    "vishvas news",
    "pib fact check",
}

# Domain validation prevents an unrelated site from gaining trusted status by
# merely labelling its feed metadata "Reuters" or "BBC". Google News wrappers
# are permitted only when their publisher metadata is on the name allowlist.
ESTABLISHED_DOMAINS = {
    "reuters.com", "apnews.com", "ap.org", "bbc.com", "bbc.co.uk",
    "theguardian.com", "npr.org", "nytimes.com", "washingtonpost.com",
    "cnn.com", "cnbc.com", "bloomberg.com", "ft.com", "wsj.com",
    "espn.com", "nature.com", "science.org", "statnews.com",
    "aljazeera.com", "snopes.com", "politifact.com", "factcheck.org",
    "fullfact.org", "afp.com", "usatoday.com", "theverge.com",
    "arstechnica.com", "techcrunch.com", "wired.com", "technologyreview.com",
    "hollywoodreporter.com", "variety.com", "edweek.org", "insidehighered.com",
    "news.un.org", "who.int", "nasa.gov", "noaa.gov", "pbs.org",
    "abcnews.go.com", "cbsnews.com", "nbcnews.com", "axios.com",
    "politico.com", "theatlantic.com", "economist.com", "forbes.com",
    "fortune.com", "businessinsider.com", "sky.com", "france24.com",
    "dw.com", "cbc.ca", "smh.com.au", "scmp.com",
    "timesofindia.indiatimes.com", "thehindu.com", "indianexpress.com",
    "ndtv.com", "wionews.com", "hindustantimes.com", "indiatoday.in",
    "economictimes.indiatimes.com", "livemint.com", "business-standard.com",
    "ptinews.com", "news18.com", "firstpost.com", "theprint.in",
    "scroll.in", "thewire.in", "boomlive.in", "altnews.in", "factly.in",
    "newschecker.in", "vishvasnews.com", "pib.gov.in", "telegraph.co.uk",
}

DISCLAIMER = (
    "This is an automated, informational assessment based on publicly available "
    "reporting retrieved at the time of analysis. It is not a definitive verdict, "
    "legal finding, or substitute for professional fact-checking. Always read the "
    "cited sources."
)

# Weighted language cues. Explicit confirmation/correction language counts more
# than a neutral attribution phrase such as "according to".
SUPPORT_CUES = {
    "confirms": 2,
    "confirmed": 2,
    "fact check: true": 3,
    "claim is true": 3,
    "found to be true": 3,
    "accurate": 2,
    "verified": 2,
    "verifies": 2,
    "announces": 2,
    "announced": 2,
    "according to": 1,
    "official statement": 1,
    "data shows": 1,
    "records show": 1,
    "evidence shows": 1,
    "study finds": 1,
    "reported that": 1,
    "said on record": 1,
}
CONTRADICT_CUES = {
    "false": 2,
    "fake": 2,
    "debunk": 2,
    "debunked": 2,
    "denies": 2,
    "denied": 2,
    "refutes": 2,
    "refuted": 2,
    "no evidence": 2,
    "not true": 2,
    "untrue": 2,
    "hoax": 2,
    "fact check: false": 3,
    "claim is false": 3,
    "found to be false": 3,
    "baseless": 2,
    "fabricated": 2,
    "incorrect": 1,
    "misleading": 1,
    "rumour": 1,
    "rumor": 1,
    "disputed": 1,
    "contradicts": 1,
    "contrary to": 1,
    "misinformation": 1,
}
# Reporting verbs and filler do not identify what a claim asserts; they are
# ignored when measuring how much of the claim an evidence item actually covers.
GENERIC_CLAIM_WORDS = {
    "confirm", "confirms", "confirmed", "confirmation", "announce", "announces",
    "announced", "report", "reports", "reported", "say", "says", "said",
    "according", "official", "officials", "statement", "data", "show", "shows",
    "showed", "new", "recently", "today", "yesterday", "week", "year", "claim",
    "claims", "claimed", "will", "would", "could", "should", "may", "might",
    "also", "more", "most", "some", "many", "much", "very", "just", "about",
}

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been", "it",
    "its", "this", "that", "these", "those", "has", "have", "had", "will",
    "would", "can", "could", "should", "says", "said", "new", "news", "about",
    "after", "before", "over", "under", "more", "than", "into", "also", "just",
    "they", "their", "there", "been", "who", "what", "when", "where", "why",
    "how", "not", "no", "all", "any", "his", "her", "him", "she", "he", "you",
    "your", "our", "we", "us", "do", "does", "did", "so", "if", "then", "up",
}
_WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9'-]+")


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in _WORD_RE.findall(text or ""):
        token = raw.lower().strip("'-")
        if token in STOPWORDS or len(token) <= 2:
            continue
        tokens.add(NUMBER_WORDS.get(token, token))
    # Collapse simple plurals so "rates" matches "rate".
    normalized = set()
    for token in tokens:
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            normalized.add(token[:-1])
        else:
            normalized.add(token)
    return normalized


def _content_tokens(tokens: set[str]) -> set[str]:
    content = tokens - GENERIC_CLAIM_WORDS
    return content or tokens


def _claim_core(claim: str, article_title: str = "", content: str = "") -> str:
    raw = (claim or "").strip()
    if not raw and article_title:
        raw = article_title.strip()
    if not raw and content:
        raw = content.strip()
    raw = clean_text(raw, 900)
    # Keep the first two sentences: long paragraphs bury the actual assertion.
    sentences = re.split(r"(?<=[.!?])\s+", raw)
    core = " ".join(sentences[:2]).strip()
    if not core:
        return ""
    return clean_text(core, 500)


def _page_metadata(url: str) -> dict:
    if not url:
        return {}
    try:
        response = requests.get(
            url,
            timeout=min(settings.NEWSHUB["FETCH_TIMEOUT"], 8),
            headers={"User-Agent": settings.NEWSHUB["USER_AGENT"]},
        )
        if response.status_code >= 400:
            return {}
        soup = BeautifulSoup(response.text[:400000], "html.parser")
        title = ""
        description = ""
        for attribute, key in (("property", "og:title"), ("name", "twitter:title")):
            tag = soup.find("meta", attrs={attribute: key})
            if tag and tag.get("content"):
                title = title or clean_text(tag["content"], 300)
        if soup.title and soup.title.string:
            title = title or clean_text(soup.title.string, 300)
        for attribute, key in (
            ("property", "og:description"),
            ("name", "description"),
            ("name", "twitter:description"),
        ):
            tag = soup.find("meta", attrs={attribute: key})
            if tag and tag.get("content"):
                description = description or clean_text(tag["content"], 600)
        return {"title": title, "description": description}
    except requests.RequestException:
        return {}
    except Exception as exc:  # noqa: BLE001 - metadata is best effort
        logger.info("Metadata fetch failed for %s: %s", url, exc)
        return {}


def _queries(claim: str) -> list[str]:
    """Build distinct exact, broad and fact-check searches without scrambling terms."""
    normalized = clean_text(claim, 240).strip().strip('"')
    keywords = [token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]+", normalized)
                if token.lower() not in STOPWORDS and len(token) > 2]
    compact = " ".join(keywords[:7])
    queries: list[str] = []
    if normalized:
        queries.append(f'"{normalized[:180]}"')
    if compact and compact.lower() != normalized.lower():
        queries.append(compact)
        queries.append(f'"{compact}" fact check')
    elif compact:
        queries.append(f'"{compact}" fact check')
    # Indian fact-checking desks and international fact-checkers are explicitly
    # included, but search results remain evidence candidates, not a verdict.
    if compact:
        queries.append(f'"{compact}" (fact check OR debunked OR verified)')
    return list(dict.fromkeys(query for query in queries if query))


def _stance(claim_tokens: set[str], item: NormalizedArticle) -> dict:
    """Classify a retrieved item only when it discusses the claim's specifics.

    Lexical overlap is a retrieval aid, not semantic proof. A source that shares
    only a broad word (for example, "contract") is rejected as weak evidence.
    Contradiction requires a relevant correction/denial cue or an explicit
    negation in a sentence that also contains several claim-specific terms.
    """
    title = item.title or ""
    description = item.description or ""
    content = getattr(item, "content", "") or ""
    text = f"{title}. {description}. {content}".lower()
    text_tokens = _tokens(text)
    focus = _content_tokens(claim_tokens)
    matched = focus & text_tokens
    coverage = len(matched) / max(len(focus), 1)
    title_matched = focus & _tokens(title)

    # Long claims require at least three distinct terms, with a useful fraction
    # of the claim covered. Very short claims require two distinct terms.
    min_matches = 2 if len(focus) <= 4 else 3
    relevant = len(matched) >= min_matches and coverage >= 0.20
    if not relevant:
        return {
            "stance": "weak",
            "relevance": round(min(1.0, len(matched) / max(min_matches, 1)), 3),
            "weight": 0.0,
            "coverage": round(coverage, 3),
            "matched_terms": sorted(matched)[:8],
            "support_hits": 0,
            "contradict_hits": 0,
        }

    support_hits = 0
    contradict_hits = 0
    negation_patterns = (
        r"\b(?:did|does|do|was|were|is|are|has|have|had|will|would|can|could)\s+not\b",
        r"\bnever\b",
        r"\bno\s+(?:such|evidence|record|official|confirmed)\b",
        r"\bnot\s+(?:true|accurate|correct|confirmed|happen|occur)\b",
    )
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence_tokens = _tokens(sentence)
        sentence_matches = focus & sentence_tokens
        if len(sentence_matches) < min(2, min_matches):
            continue
        support_hits += sum(weight for cue, weight in SUPPORT_CUES.items() if cue in sentence)
        contradict_hits += sum(weight for cue, weight in CONTRADICT_CUES.items() if cue in sentence)
        if any(re.search(pattern, sentence) for pattern in negation_patterns):
            contradict_hits += 2

    # Direct reporting can support an event claim without using "confirmed".
    strong_coverage = coverage >= 0.68 and len(matched) >= max(4, min_matches)
    can_support = (
        (support_hits >= 2 or strong_coverage)
        and len(matched) >= min_matches
        and coverage >= 0.35
    )
    can_contradict = (
        contradict_hits >= 2
        and len(matched) >= min_matches
        and coverage >= 0.25
    )

    if can_contradict and (not can_support or contradict_hits >= support_hits):
        stance = "contradicting"
    elif can_support:
        stance = "supporting"
    elif len(matched) >= min_matches and coverage >= 0.20:
        stance = "context"
    else:
        stance = "weak"

    relevance = round(min(1.0, 0.55 * coverage + 0.45 * len(title_matched) / max(len(focus), 1)), 3)
    weight = round(
        min(0.9, 0.45 * relevance + 0.25 * coverage + 0.035 * (support_hits + contradict_hits)),
        3,
    )
    return {
        "stance": stance,
        "relevance": relevance,
        "weight": weight,
        "coverage": round(coverage, 3),
        "matched_terms": sorted(matched)[:8],
        "support_hits": support_hits,
        "contradict_hits": contradict_hits,
    }


def _is_established(source: str, url: str = "") -> bool:
    name = " ".join((source or "").lower().split())
    if not name:
        return False
    name_ok = name in ESTABLISHED_SOURCES or any(
        name.startswith(f"{trusted} ") for trusted in ESTABLISHED_SOURCES if len(trusted) > 4
    )
    if not name_ok:
        return False
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return False
    if host in {"news.google.com", "news.googleusercontent.com"}:
        return True
    return bool(host) and any(host == domain or host.endswith("." + domain) for domain in ESTABLISHED_DOMAINS)


def _publisher_key(item: dict) -> str:
    """Return a stable publisher identity so syndicated URLs are not independent."""
    url = str(item.get("url") or "")
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        host = ""
    if host in {"news.google.com", "news.googleusercontent.com"}:
        return "google-news:" + " ".join(str(item.get("source") or "").lower().split())
    return host or "source:" + " ".join(str(item.get("source") or "").lower().split())


def _independent_publisher_count(items: list[dict]) -> int:
    """Count distinct publisher domains while discounting near-identical wire copies."""
    accepted_domains: set[str] = set()
    accepted_texts: list[set[str]] = []
    ordered = sorted(items, key=lambda item: float(item.get("weight", 0)), reverse=True)
    for item in ordered:
        publisher = _publisher_key(item)
        if not publisher or publisher in accepted_domains:
            continue
        text_tokens = _tokens(f"{item.get('title', '')} {item.get('excerpt', '')}")
        if len(text_tokens) >= 6:
            syndicated_copy = False
            for previous in accepted_texts:
                union = text_tokens | previous
                similarity = len(text_tokens & previous) / max(len(union), 1)
                if similarity >= 0.88:
                    syndicated_copy = True
                    break
            if syndicated_copy:
                continue
        accepted_domains.add(publisher)
        if text_tokens:
            accepted_texts.append(text_tokens)
    return len(accepted_domains)


def _verdict(scored: list[dict]) -> tuple[str, float]:
    """Apply conservative thresholds and require publisher independence.

    A single ordinary news report is not enough to label a claim supported or
    contradicted. Conflicting relevant reporting is surfaced as Mixed even if
    one side comes from a publisher outside the allowlist; the allowlist is
    still required for a one-direction verdict.
    """
    material = [
        item for item in scored
        if item.get("stance") in {"supporting", "contradicting"}
        and item.get("relevance", 0) >= 0.28
        and item.get("weight", 0) >= 0.20
    ]
    supporting_all = [item for item in material if item["stance"] == "supporting"]
    contradicting_all = [item for item in material if item["stance"] == "contradicting"]
    supporting = [item for item in supporting_all if item.get("trusted")]
    contradicting = [item for item in contradicting_all if item.get("trusted")]

    support_sources = _independent_publisher_count(supporting)
    contradict_sources = _independent_publisher_count(contradicting)

    def is_dedicated_fact_check(source: str) -> bool:
        name = " ".join((source or "").lower().split())
        return name in FACT_CHECK_SOURCES or any(
            name.startswith(f"{trusted} ") for trusted in FACT_CHECK_SOURCES
        )

    dedicated_support = any(is_dedicated_fact_check(item["source"]) for item in supporting)
    dedicated_contradiction = any(is_dedicated_fact_check(item["source"]) for item in contradicting)

    # Never show a one-sided result when the retrieved relevant evidence points
    # in both directions. This specifically fixes a supported label with a
    # simultaneously displayed contradicting item.
    if supporting_all and contradicting_all and (supporting or contradicting):
        return FactCheck.Verdict.MIXED.value, 0.42

    if contradict_sources >= 2 or (dedicated_contradiction and not supporting_all):
        confidence = min(0.78, 0.48 + 0.06 * min(contradict_sources, 3))
        return FactCheck.Verdict.CONTRADICTED.value, round(confidence, 2)

    if support_sources >= 2 or (dedicated_support and not contradicting_all):
        confidence = 0.62 if support_sources >= 2 else 0.56
        return FactCheck.Verdict.SUPPORTED.value, confidence

    # One ordinary publisher report is useful context, not enough for a
    # definitive directional verdict. One-off evidence is therefore cautious.
    if supporting_all or contradicting_all:
        return FactCheck.Verdict.INSUFFICIENT.value, 0.24

    return FactCheck.Verdict.INSUFFICIENT.value, 0.10


def _templated_explanation(verdict: str, claim: str, scored: list[dict], sources: int) -> str:
    material = [
        item for item in scored
        if item.get("stance") in {"supporting", "contradicting"}
        and item.get("relevance", 0) >= 0.28
        and item.get("weight", 0) >= 0.20
    ]
    supporting_all = sum(1 for item in material if item["stance"] == "supporting")
    contradicting_all = sum(1 for item in material if item["stance"] == "contradicting")
    supporting_trusted_items = [item for item in material if item["stance"] == "supporting" and item.get("trusted")]
    contradicting_trusted_items = [item for item in material if item["stance"] == "contradicting" and item.get("trusted")]
    supporting_trusted = _independent_publisher_count(supporting_trusted_items)
    contradicting_trusted = _independent_publisher_count(contradicting_trusted_items)
    context = sum(1 for item in scored if item["stance"] == "context")
    relevant = len(material) + context

    if verdict == FactCheck.Verdict.INSUFFICIENT.value:
        if relevant == len(scored):
            summary = (
                f"NewsHub retrieved {len(scored)} related item(s) for this claim, but none "
                "provided enough independent, claim-specific evidence for a directional assessment."
            )
        else:
            summary = (
                f"NewsHub retrieved {len(scored)} items for this claim and only {relevant} "
                "were sufficiently related to count as evidence or context."
            )
        return (
            f"{summary} That is not enough to assess the claim either way. "
            "'No evidence found' means the search did not surface adequate reliable reporting; "
            "it does not mean the claim is false."
        )
    if verdict == FactCheck.Verdict.CONTRADICTED.value:
        return (
            f"{contradicting_trusted} independent item(s) from established publishers contain "
            "relevant correction, denial or contradictory reporting. The automated assessment "
            "therefore labels the claim as contradicted by the available evidence; it is not a "
            "definitive finding that every detail is false."
        )
    if verdict == FactCheck.Verdict.SUPPORTED.value:
        return (
            f"{supporting_trusted} independent item(s) from established publishers support the "
            "claim or report its key details. This indicates corroborating coverage, not independent proof "
            "that every detail is accurate."
        )
    return (
        f"The retrieved reports conflict: {supporting_all} item(s) contain reporting consistent "
        f"with the claim and {contradicting_all} contain relevant contradictory or correcting "
        f"information. Of these, {supporting_trusted} supporting and {contradicting_trusted} "
        f"contradicting item(s) are from established publishers. The available evidence does "
        "not support a one-direction conclusion."
    )


def _best_evidence_excerpt(item: NormalizedArticle, claim_tokens: set[str], limit: int = 320) -> str:
    """Prefer a relevant sentence from content/description over a generic snippet."""
    parts = [getattr(item, "content", "") or "", item.description or "", item.title or ""]
    sentences: list[str] = []
    for part in parts:
        sentences.extend(re.split(r"(?<=[.!?])\s+", clean_text(part, 12000)))
    scored_sentences = []
    focus = _content_tokens(claim_tokens)
    for sentence in sentences:
        sentence = clean_text(sentence, 600)
        if len(sentence) < 35:
            continue
        overlap = len(focus & _tokens(sentence))
        if overlap:
            scored_sentences.append((overlap, len(_tokens(sentence)), sentence))
    if scored_sentences:
        scored_sentences.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        return clean_text(scored_sentences[0][2], limit)
    return clean_text(item.description or item.title, limit)

def _llm_explanation(claim: str, verdict: str, scored: list[dict]) -> tuple[str, str]:
    """Return (explanation, engine). The LLM may not change the verdict."""
    if not is_llm_enabled():
        return "", ""
    evidence_text = "\n".join(
        f"- [{item['stance']}] {item['title']} ({item['source'] or 'unknown source'}): {item.get('excerpt', '')}"
        for item in scored[:8]
    )
    prompt = (
        "You explain an automated evidence review. Do not change the verdict, do not add "
        "sources that are not listed, and do not assert the claim is proven true or false. "
        "Write 2-3 plain sentences for a general reader, citing the listed outlets by name "
        "where relevant, and state the limitation that this is an automated assessment.\n\n"
        f"Claim: {claim}\n"
        f"Verdict label: {verdict}\n"
        f"Retrieved evidence:\n{evidence_text or '- none'}"
    )
    try:
        explanation = chat_completion(
            [
                {"role": "system", "content": "You write careful, neutral news analysis."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=260,
            temperature=0.2,
        )
        return explanation, "llm_explanation"
    except Exception as exc:  # noqa: BLE001 - explanation is optional
        logger.info("LLM explanation unavailable: %s", exc)
        return "", ""


def analyze_claim(
    claim: str = "",
    article_title: str = "",
    source_url: str = "",
    content: str = "",
) -> dict:
    """Run the full evidence workflow and return a structured assessment."""
    if not any([claim.strip(), article_title.strip(), content.strip(), source_url.strip()]):
        raise ValueError("Provide a claim, headline, article URL or paragraph to analyze.")

    metadata = _page_metadata(source_url) if source_url else {}
    if not article_title and metadata.get("title"):
        article_title = metadata["title"]
    claim_core = _claim_core(claim, article_title, content or metadata.get("description", ""))
    if not claim_core:
        raise ValueError("A claim or article headline is required for analysis.")

    claim_tokens = _tokens(claim_core)
    queries = _queries(claim_core) if claim_tokens else [claim_core]

    raw_items: list[NormalizedArticle] = []
    provider_errors: list[str] = []
    providers_attempted = 0
    providers_succeeded = 0

    def run_query(query: str):
        return search_external(query, limit=30)

    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
        for result in pool.map(run_query, queries):
            providers_attempted += result.providers_attempted
            providers_succeeded += result.providers_succeeded
            provider_errors.extend(result.errors)
            raw_items.extend(result.articles)

    # Stored NewsHub coverage is also useful evidence context, particularly if
    # one external provider is temporarily unavailable.
    try:
        for stored in Article.objects.published().order_by("-published_at")[:350]:
            raw_items.append(NormalizedArticle(
                title=stored.title,
                source_url=stored.source_url,
                source_name=stored.source_name,
                description=stored.description,
                content=stored.content,
                published_at=stored.published_at,
                provider="newshub_database",
            ))
    except Exception as exc:  # noqa: BLE001
        logger.info("Could not include stored article evidence: %s", exc)

    seen_urls: set[str] = set()
    if source_url:
        seen_urls.add(normalize_url(source_url))
    scored: list[dict] = []
    for item in raw_items:
        canonical = normalize_url(item.source_url)
        if not canonical or canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        analysis = _stance(claim_tokens, item)
        if analysis["stance"] == "weak":
            # Retain modestly relevant context for transparency, but these items
            # never contribute to the supported/contradicted verdict.
            item_tokens = _tokens(f"{item.title} {item.description} {item.content}")
            shared = _content_tokens(claim_tokens) & item_tokens
            minimum_context_terms = 2 if len(_content_tokens(claim_tokens)) <= 4 else 3
            if len(shared) < minimum_context_terms:
                continue
            analysis["stance"] = "context"
            analysis["relevance"] = round(min(0.65, len(shared) / max(len(_content_tokens(claim_tokens)), 1)), 3)
            analysis["weight"] = round(min(0.35, analysis["relevance"] * 0.45), 3)
            analysis["matched_terms"] = sorted(shared)[:8]
        source_name = clean_text(item.source_name, 150)
        scored.append(
            {
                "title": clean_text(item.title, 300),
                "url": item.source_url,
                "source": source_name,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "excerpt": _best_evidence_excerpt(item, claim_tokens, 320),
                "publisher_key": _publisher_key({"url": item.source_url, "source": source_name}),
                "domain": normalize_url(item.source_url).split("//")[-1].split("/")[0],
                "trusted": _is_established(source_name, item.source_url),
                **analysis,
            }
        )

    # Keep direct supporting/contradicting items ahead of generic context so
    # a meaningful conflict is not accidentally truncated from the verdict.
    scored.sort(
        key=lambda item: (
            item["stance"] in {"supporting", "contradicting"},
            bool(item.get("trusted")),
            item["relevance"],
            item["weight"],
        ),
        reverse=True,
    )
    scored = scored[:12]

    verdict, confidence = _verdict(scored)
    distinct_sources = _independent_publisher_count(
        [item for item in scored if item.get("trusted") and item["stance"] in {"supporting", "contradicting"}]
    )
    explanation = _templated_explanation(verdict, claim_core, scored, distinct_sources)
    engine = "rule_based_evidence_analysis"

    llm_text, llm_engine = _llm_explanation(claim_core, verdict, scored)
    if llm_text:
        explanation = llm_text
        engine = f"{engine}+{llm_engine}"

    # Use the same claim-specific matcher as TruthTrace. A broad shared word
    # such as "contract" or "court" must not create a related-story link.
    related = []
    try:
        candidates = list(
            Article.objects.published().with_relations()
            .order_by("-published_at")[:300]
        )
        related_matches = find_claim_matches(claim_core, candidates, limit=5)
        for match in related_matches:
            article = match["article"]
            if source_url and normalize_url(article.source_url) == normalize_url(source_url):
                continue
            related.append({
                "id": article.id,
                "title": article.title,
                "source": article.source_name,
                "url": article.source_url,
                "similarity": match["similarity"],
                "shared_terms": match.get("shared_terms", []),
            })
    except Exception as exc:  # noqa: BLE001 - related stories are supplemental
        logger.info("Could not retrieve related stored stories: %s", exc)


    notes = {
        "method": (
            "Retrieved related coverage and fact-check reporting, scored relatedness and "
            "claim-specific term coverage and explicit support/contradiction cues, included "
            "stored NewsHub reporting, and required distinct publisher domains for directional "
            "verdicts. Conflicting relevant evidence is labelled Mixed; a single ordinary "
            "publisher report remains Insufficient."
        ),
        "queries": queries,
        "providers_attempted": providers_attempted,
        "providers_succeeded": providers_succeeded,
        "provider_errors": sorted(set(provider_errors)),
        "evidence_considered": len(scored),
        "supporting_items": sum(1 for item in scored if item["stance"] == "supporting"),
        "contradicting_items": sum(1 for item in scored if item["stance"] == "contradicting"),
        "context_items": sum(1 for item in scored if item["stance"] == "context"),
        "limitations": [
            "Automated keyword and overlap scoring can misread sarcasm, negation and context.",
            "Publisher allowlisting is a heuristic, not a certification. Local and regional outlets may not be listed yet.",
            "Coverage of a claim is not the same as independent verification of it.",
            "Publisher domains and near-identical excerpts are used to reduce duplicate/syndicated reports being counted as independent sources.",
            "Search results depend on provider availability and are not exhaustive.",
            "The LLM, when configured, writes the explanation only; it does not set the verdict.",
        ],
        "trusted_source_policy": (
            "Directional Supported/Contradicted verdicts require independent established-publisher "
            "corroboration or a dedicated fact-check source. Relevant conflict is shown as Mixed. "
            "All accepted retrieved items remain visible with their stance."
        ),
        "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    return {
        "claim": claim_core,
        "article_title": clean_text(article_title, 490),
        "source_url": source_url,
        "verdict": verdict,
        "confidence": confidence,
        "explanation": explanation,
        "evidence": scored,
        "related_articles": related,
        "analysis_notes": notes,
        "engine": engine,
        "disclaimer": DISCLAIMER,
    }


def persist_fact_check(result: dict, user=None) -> FactCheck:
    record = FactCheck.objects.create(
        user=user if user and user.is_authenticated else None,
        claim=result["claim"],
        article_title=result["article_title"],
        source_url=result["source_url"],
        verdict=result["verdict"],
        confidence=result["confidence"],
        explanation=result["explanation"],
        evidence=result["evidence"],
        related_articles=result["related_articles"],
        analysis_notes=result["analysis_notes"],
        engine=result["engine"],
    )
    return record


def serialize_fact_check(record: FactCheck) -> dict:
    return {
        "id": str(record.reference),
        "claim": record.claim,
        "article_title": record.article_title,
        "source_url": record.source_url,
        "verdict": record.verdict,
        "verdict_label": record.get_verdict_display(),
        "confidence": record.confidence,
        "explanation": record.explanation,
        "evidence": record.evidence,
        "related_articles": record.related_articles,
        "analysis_notes": record.analysis_notes,
        "engine": record.engine,
        "created_at": record.created_at.isoformat(),
        "disclaimer": DISCLAIMER,
    }
