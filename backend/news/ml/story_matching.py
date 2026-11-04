"""Event-oriented matching shared by NewsLens and TruthTrace.

This is a deterministic retrieval heuristic, not a fact-verification model.
It combines TF-IDF, normalized event terms, title coverage, named-entity
signals and publication-time proximity. Scores are ranking signals only.
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from news.models import Article

TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9'-]{1,}\b")
ENTITY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9&.'-]*)(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3}\b")
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "has", "was",
    "were", "are", "will", "would", "could", "about", "after", "before", "into",
    "over", "under", "said", "says", "their", "they", "them", "than", "then",
    "its", "his", "her", "our", "you", "your", "who", "what", "when", "where",
    "why", "how", "not", "but", "also", "been", "being", "according", "new",
    "latest", "news", "report", "reports", "reported", "amid", "say", "says",
    "did", "does", "do", "is", "are", "was", "were", "a", "an", "of", "to",
    "in", "on", "at", "by", "as", "it", "its", "their", "his", "her",
}
ENTITY_LEAD_STOPWORDS = {"why", "what", "how", "when", "where", "who", "inside", "the", "a", "an"}
ENTITY_NON_WORDS = STOPWORDS | {
    "stop", "stops", "stopped", "halt", "halts", "freeze", "freezes", "frozen",
    "pause", "pauses", "salary", "salaries", "pay", "wages", "of", "over",
    "under", "failure", "remove", "removal", "encroachment", "encroachments",
    "impose", "imposes", "imposed", "fine", "fines", "did", "does", "do",
    "wins", "won", "win", "defeats", "defeat", "beat", "beats", "beaten",
    "announces", "announced", "launches", "launched", "says", "said", "reports",
    "reported", "alleged", "alleges", "proposes", "proposed", "plans", "plan",
    "decision", "contract", "extension", "story", "update", "live", "latest",
}

# Small, transparent aliases help common India-focused coverage without relying
# on a large external model. Extend these only with well-known abbreviations.
ENTITY_ALIASES = {
    "brihanmumbai municipal corporation": "bmc",
    "mumbai municipal corporation": "bmc",
    "bombay municipal corporation": "bmc",
    "bmc": "bmc",
    "supreme court of india": "supreme court",
    "supreme court": "supreme court",
    "tdp": "tdp",
    "telugu desam party": "tdp",
    "ysrcp": "ysrcp",
    "ysr congress party": "ysrcp",
}

TOKEN_ALIASES = {
    "stops": "halt", "stop": "halt", "stopped": "halt", "stopping": "halt",
    "halts": "halt", "halted": "halt", "pauses": "halt", "paused": "halt",
    "pause": "halt", "freezes": "halt", "freeze": "halt", "froze": "halt",
    "frozen": "halt", "suspends": "halt", "suspended": "halt",
    "salary": "salary", "salaries": "salary", "pay": "salary", "wages": "salary",
    "remuneration": "salary", "commissioners": "commissioner",
    "encroachments": "encroachment", "civics": "civic",
}


def tokens(text: str) -> set[str]:
    result: set[str] = set()
    for raw in TOKEN_RE.findall(text or ""):
        word = raw.lower().strip("'-")
        if word in STOPWORDS or len(word) < 3:
            continue
        if word.endswith("'s"):
            word = word[:-2]
        elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        result.add(TOKEN_ALIASES.get(word, word))
    return result


def _canonical_entity(value: str) -> str:
    normalized = " ".join(value.lower().replace("&", "and").split()).strip(" .,'\"-:")
    return ENTITY_ALIASES.get(normalized, normalized)


def entities(text: str) -> set[str]:
    """Extract conservative capitalized names and common multi-word aliases."""
    found: set[str] = set()
    for raw in ENTITY_RE.findall(text or ""):
        words = [word.lower().strip(" .,'\"-:") for word in raw.split()]
        words = [word for word in words if word and word not in ENTITY_NON_WORDS]
        if not words:
            continue
        # Individual proper-name tokens make phrase matching robust to
        # paraphrases such as "Mumbai civic body" vs "BMC".
        found.update(word for word in words if len(word) > 2)
        for size in (2, 3):
            for offset in range(max(0, len(words) - size + 1)):
                phrase = " ".join(words[offset:offset + size])
                if phrase not in ENTITY_NON_WORDS and len(phrase) > 3:
                    found.add(_canonical_entity(phrase))
        normalized = _canonical_entity(" ".join(words))
        if normalized and len(normalized) > 2:
            found.add(normalized)
    for acronym in re.findall(r"\b[A-Z]{2,8}\b", text or ""):
        found.add(_canonical_entity(acronym))
    lowered = (text or "").lower()
    for full_name, alias in ENTITY_ALIASES.items():
        if full_name != alias and full_name in lowered:
            found.add(alias)
    return found


def _article_text(article: Article) -> str:
    return " ".join(
        part for part in (
            article.title,
            article.description or "",
            (article.content or "")[:3500],
        ) if part
    )


def _publisher_identity(article: Article) -> str:
    host = (article.publisher_domain or "").lower().removeprefix("www.")
    if host in {"news.google.com", "news.googleusercontent.com"}:
        source = re.sub(r"\s*\(via google news\)\s*", " ", (article.source_name or "").lower())
        return "google-news:" + " ".join(source.split())
    return host


def _time_score(left: datetime | None, right: datetime | None) -> float:
    if not left or not right:
        return 0.5
    try:
        delta_days = abs((left - right).total_seconds()) / 86400
    except TypeError:
        return 0.5
    return math.exp(-delta_days / 12.0)


def _dice_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    common = len(left & right)
    return (2.0 * common) / (len(left) + len(right))


def _entity_recall(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _score_pair(
    title_overlap: float = 0.0,
    entity_overlap: float = 0.0,
    context_overlap: float = 0.0,
    time_score: float = 0.5,
    tfidf_score: float = 0.0,
) -> float:
    """Score how likely two reports describe the same event.

    Category equality is deliberately excluded: two stories in Politics are
    not necessarily the same event. Overlap is normalized symmetrically so a
    short paraphrased headline is not excessively penalized by a longer one.
    """
    score = (
        0.30 * tfidf_score
        + 0.24 * title_overlap
        + 0.22 * entity_overlap
        + 0.16 * context_overlap
        + 0.08 * time_score
    )
    return min(1.0, max(0.0, score))


def find_story_matches(anchor: Article, limit: int = 8, candidate_limit: int = 500) -> list[dict]:
    """Retrieve likely same-event coverage from other publishers."""
    candidates = list(
        Article.objects.published().with_relations()
        .exclude(pk=anchor.pk)
        .order_by("-published_at")[:candidate_limit]
    )
    if not candidates:
        return []

    anchor_text = _article_text(anchor)
    docs = [anchor_text] + [_article_text(item) for item in candidates]
    try:
        matrix = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), max_features=30000,
            sublinear_tf=True,
        ).fit_transform(docs)
        tfidf_scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except ValueError:
        tfidf_scores = [0.0] * len(candidates)

    anchor_title_tokens = tokens(anchor.title)
    anchor_context_tokens = tokens(f"{anchor.title} {anchor.description} {(anchor.content or '')[:2500]}")
    anchor_entities = entities(f"{anchor.title} {anchor.description} {(anchor.content or '')[:1200]}")
    anchor_title_entities = entities(anchor.title)
    scored: list[dict] = []
    per_publisher: dict[str, int] = {}
    anchor_host = _publisher_identity(anchor)

    for index, candidate in enumerate(candidates):
        host = _publisher_identity(candidate)
        if not host or host == anchor_host:
            continue
        candidate_title_tokens = tokens(candidate.title)
        candidate_context_tokens = tokens(
            f"{candidate.title} {candidate.description} {(candidate.content or '')[:2500]}"
        )
        candidate_entities = entities(
            f"{candidate.title} {candidate.description} {(candidate.content or '')[:1200]}"
        )
        candidate_title_entities = entities(candidate.title)
        common_entities = anchor_entities & candidate_entities
        title_common = anchor_title_tokens & candidate_title_tokens
        title_overlap = _dice_overlap(anchor_title_tokens, candidate_title_tokens)
        context_overlap = _dice_overlap(anchor_context_tokens, candidate_context_tokens)
        anchor_entity_words = {word for value in anchor_title_entities for word in value.split()}
        candidate_entity_words = {word for value in candidate_title_entities for word in value.split()}
        anchor_event_terms = anchor_title_tokens - anchor_entity_words
        candidate_event_terms = candidate_title_tokens - candidate_entity_words
        shared_event_terms = anchor_event_terms & candidate_event_terms
        event_overlap = _dice_overlap(anchor_event_terms, candidate_event_terms)
        entity_overlap = max(
            _entity_recall(anchor_title_entities, candidate_title_entities),
            0.75 * _entity_recall(anchor_entities, candidate_entities),
        )
        tfidf_score = float(tfidf_scores[index])
        time_score = _time_score(anchor.published_at, candidate.published_at)
        score = _score_pair(title_overlap, entity_overlap, context_overlap, time_score, tfidf_score)
        # Event-action overlap rewards reports that describe the same action,
        # while preventing a shared institution/location alone from dominating.
        score = min(1.0, score + 0.10 * event_overlap)

        # A same-event match needs at least one specific signal: multiple shared
        # title terms, a named-entity match plus contextual overlap, or strong
        # TF-IDF and title similarity. Shared category is never sufficient.
        entity_signal = (
            bool(common_entities)
            and context_overlap >= 0.10
            and len(shared_event_terms) >= 2
        )
        lexical_signal = len(shared_event_terms) >= 3 and title_overlap >= 0.18
        semantic_signal = tfidf_score >= 0.20 and title_overlap >= 0.16 and len(shared_event_terms) >= 2
        if score < 0.22 or not (entity_signal or lexical_signal or semantic_signal):
            continue

        publisher_count = per_publisher.get(host, 0)
        if publisher_count >= 2:
            continue
        per_publisher[host] = publisher_count + 1

        reasons = []
        if common_entities:
            reasons.append("shared entities: " + ", ".join(sorted(common_entities)[:3]))
        if title_overlap >= 0.20 or context_overlap >= 0.22 or tfidf_score >= 0.20:
            reasons.append("similar headline and article context")
        if shared_event_terms:
            reasons.append("shared event terms: " + ", ".join(sorted(shared_event_terms)[:3]))
        if time_score >= 0.75:
            reasons.append("published in a similar time window")
        scored.append({
            "article": candidate,
            "similarity": round(score, 3),
            "tfidf_similarity": round(tfidf_score, 3),
            "shared_entities": sorted(common_entities)[:6],
            "shared_topics": sorted(title_common | shared_event_terms)[:8],
            "shared_event_terms": sorted(shared_event_terms)[:8],
            "match_reason": "; ".join(reasons) or "overlapping event terms",
        })

    scored.sort(key=lambda item: (item["similarity"], item["tfidf_similarity"]), reverse=True)
    return scored[:limit]


def find_claim_matches(claim: str, candidates: list[Article], limit: int = 10) -> list[dict]:
    """Retrieve articles relevant to the specific claim, not just its broad topic."""
    claim = (claim or "").strip()
    claim_tokens = tokens(claim)
    claim_entities = entities(claim)
    if len(claim_tokens) < 2 or not candidates:
        return []

    docs = [claim] + [_article_text(item) for item in candidates]
    try:
        matrix = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), max_features=30000,
            sublinear_tf=True,
        ).fit_transform(docs)
        tfidf_scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except ValueError:
        tfidf_scores = [0.0] * len(candidates)

    results = []
    for index, article in enumerate(candidates):
        title_tokens = tokens(article.title)
        article_tokens = tokens(
            f"{article.title} {article.description or ''} {(article.content or '')[:2500]}"
        )
        shared_terms = claim_tokens & article_tokens
        coverage = len(shared_terms) / max(len(claim_tokens), 1)
        title_coverage = len(claim_tokens & title_tokens) / max(len(claim_tokens), 1)
        article_entities = entities(
            f"{article.title} {article.description or ''} {(article.content or '')[:1200]}"
        )
        shared_entities = claim_entities & article_entities
        entity_score = _entity_recall(claim_entities, article_entities)
        tfidf_score = float(tfidf_scores[index])
        score = (
            0.42 * tfidf_score
            + 0.24 * coverage
            + 0.16 * title_coverage
            + 0.18 * entity_score
        )

        # Suppress false matches that share only a broad word (e.g. "contract")
        # or category. Claims with explicit entities must match an entity or
        # cover several distinct claim terms in the article itself.
        enough_terms = len(shared_terms) >= (2 if len(claim_tokens) <= 4 else 3)
        entity_anchor = bool(claim_entities & article_entities)
        specific_match = (
            (enough_terms and coverage >= 0.20)
            or (entity_anchor and len(shared_terms) >= 2 and (title_coverage >= 0.10 or tfidf_score >= 0.12))
        )
        if score < 0.17 or not specific_match:
            continue

        results.append({
            "article": article,
            "similarity": round(score, 3),
            "tfidf_similarity": round(tfidf_score, 3),
            "claim_coverage": round(coverage, 3),
            "title_coverage": round(title_coverage, 3),
            "shared_entities": sorted(shared_entities)[:6],
            "shared_terms": sorted(shared_terms)[:10],
        })
    results.sort(key=lambda item: item["similarity"], reverse=True)
    return results[:limit]
