"""Sentiment analysis using the pretrained VADER lexicon model.

VADER scores the *tone of the language*, not the accuracy of the article.
If the optional dependency is unavailable, a small built-in lexicon is used and
the response reports that fallback explicitly.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("newshub.ml")

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

try:  # pragma: no cover - import guard
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    _analyzer = SentimentIntensityAnalyzer()
except Exception as exc:  # noqa: BLE001
    _analyzer = None
    logger.warning("VADER unavailable, using fallback lexicon: %s", exc)

FALLBACK_POSITIVE = {
    "growth", "gain", "win", "wins", "record", "improve", "improved", "improves",
    "success", "successful", "boost", "strong", "profit", "profits", "rise",
    "rises", "recover", "recovery", "celebrate", "agreement", "hope", "hopeful",
    "benefit", "progress", "expand", "expansion", "award", "breakthrough",
    "support", "safe", "effective", "approve", "approved", "rally", "surge",
}
FALLBACK_NEGATIVE = {
    "loss", "losses", "crash", "decline", "declines", "fall", "falls", "risk",
    "risks", "warning", "warns", "attack", "attacks", "crisis", "concern",
    "concerns", "fear", "fears", "threat", "threats", "killed", "death",
    "deaths", "damage", "flood", "floods", "war", "conflict", "shortage",
    "delay", "delays", "fail", "fails", "failure", "cut", "cuts", "layoff",
    "layoffs", "protest", "protesters", "outbreak", "collapse", "fraud",
}


def _vader_score(text: str) -> tuple[float, dict]:
    scores = _analyzer.polarity_scores(text)
    return float(scores["compound"]), scores


def _fallback_score(text: str) -> tuple[float, dict]:
    tokens = [token.strip(".,!?;:\"'()[]").lower() for token in text.split()]
    tokens = [token for token in tokens if token]
    positive = sum(1 for token in tokens if token in FALLBACK_POSITIVE)
    negative = sum(1 for token in tokens if token in FALLBACK_NEGATIVE)
    total = positive + negative
    compound = 0.0 if total == 0 else (positive - negative) / total
    return compound, {"pos": positive, "neg": negative, "neu": len(tokens) - total}


def _label(compound: float) -> str:
    if compound >= POSITIVE_THRESHOLD:
        return "positive"
    if compound <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def analyze_sentiment(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {
            "label": "neutral",
            "score": 0.0,
            "method": "none",
            "explanation": "No text was supplied, so no sentiment could be measured.",
            "scores": {},
        }
    if _analyzer is not None:
        compound, raw = _vader_score(text)
        method = "vader_lexicon"
        explanation = (
            "VADER is a lexicon and rule based model that scores the tone of the wording. "
            "It describes language, not factual accuracy."
        )
    else:
        compound, raw = _fallback_score(text)
        method = "builtin_lexicon_fallback"
        explanation = (
            "The pretrained VADER model was unavailable, so a small built-in lexicon "
            "was used. This is a coarser estimate of tone, not a statement of accuracy."
        )
    return {
        "label": _label(compound),
        "score": round(compound, 4),
        "method": method,
        "explanation": explanation,
        "scores": raw,
    }


def sentiment_for_article(article) -> dict:
    if article.sentiment_label:
        return {
            "label": article.sentiment_label,
            "score": article.sentiment_score if article.sentiment_score is not None else 0.0,
            "method": "vader_lexicon",
            "explanation": (
                "Sentiment describes the tone of the wording, not whether the article is accurate."
            ),
            "scores": {},
        }
    return analyze_sentiment(" ".join([article.title, article.description]))
