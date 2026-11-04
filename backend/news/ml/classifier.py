"""Automatic news categorization: TF-IDF + Logistic Regression.

The model is trained locally from `news/ml/data/training_data.csv` (a curated
seed corpus written for this project) and evaluated on a held-out split. Run
`python manage.py train_classifier` to retrain and print real metrics.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

logger = logging.getLogger("newshub.ml")

ARTIFACT_DIR: Path = settings.ML_ARTIFACT_DIR
MODEL_PATH = ARTIFACT_DIR / "category_model.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"
DATASET_PATH = Path(__file__).resolve().parent / "data" / "training_data.csv"

# The classifier predicts the eight editorial categories defined in the project
# brief. "World News" is not a model class: international coverage is labelled
# from provider metadata and stays available for browsing.
LABELS = [
    "technology",
    "politics",
    "business",
    "sports",
    "entertainment",
    "health",
    "education",
    "science",
]
EXCLUDED_LABELS = ["world"]

MIN_CONFIDENCE = 0.25

_model: Pipeline | None = None
_model_mtime: float | None = None


def dataset_fingerprint() -> str:
    import hashlib

    if not DATASET_PATH.exists():
        return ""
    return hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()[:16]


def build_pipeline() -> Pipeline:
    """Word n-grams plus character n-grams help with short news headlines."""
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    stop_words="english",
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                    max_features=30000,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=30000,
                ),
            ),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            (
                "clf",
                LogisticRegression(
                    max_iter=4000,
                    C=1.0,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )


def train_model() -> dict:
    """Train on the seed corpus, evaluate on a stratified hold-out split."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Training dataset missing at {DATASET_PATH}")

    raw = pd.read_csv(DATASET_PATH).dropna(subset=["category", "title"])
    frame = raw[raw["category"].isin(LABELS)].copy()
    frame["text"] = (
        frame["title"].fillna("") + ". " + frame["description"].fillna("")
    ).str.strip()
    frame = frame[frame["text"].str.len() > 0]
    if frame["category"].nunique() < 2:
        raise ValueError("Training data must contain at least two categories.")

    x_train, x_test, y_train, y_test = train_test_split(
        frame["text"],
        frame["category"],
        test_size=0.25,
        random_state=42,
        stratify=frame["category"],
    )

    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)

    labels = sorted(frame["category"].unique().tolist())
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, predictions, labels=labels, zero_division=0
    )
    macro = precision_recall_fscore_support(
        y_test, predictions, labels=labels, average="macro", zero_division=0
    )
    weighted = precision_recall_fscore_support(
        y_test, predictions, labels=labels, average="weighted", zero_division=0
    )
    matrix = confusion_matrix(y_test, predictions, labels=labels)

    metrics = {
        "available": True,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "dataset": str(DATASET_PATH.name),
        "dataset_rows": int(len(frame)),
        "excluded_rows": int(len(raw) - len(frame)),
        "excluded_labels": EXCLUDED_LABELS,
        "rows_in_file": int(len(raw)),
        "dataset_fingerprint": dataset_fingerprint(),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "labels": labels,
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "macro_precision": round(float(macro[0]), 4),
        "macro_recall": round(float(macro[1]), 4),
        "macro_f1": round(float(macro[2]), 4),
        "weighted_precision": round(float(weighted[0]), 4),
        "weighted_recall": round(float(weighted[1]), 4),
        "weighted_f1": round(float(weighted[2]), 4),
        "per_class": {
            label: {
                "precision": round(float(precision[i]), 4),
                "recall": round(float(recall[i]), 4),
                "f1": round(float(f1[i]), 4),
                "support": int(support[i]),
            }
            for i, label in enumerate(labels)
        },
        "confusion_matrix": {
            "labels": labels,
            "matrix": matrix.tolist(),
        },
        "report": classification_report(
            y_test, predictions, labels=labels, zero_division=0, output_dict=True
        ),
        "vectorizer": "TF-IDF word(1,2) + char_wb(3,5), sublinear_tf",
        "estimator": "LogisticRegression(C=1.0, class_weight=balanced)",
        "excluded_note": (
            "World News rows are excluded from model training because that section is "
            "assigned from provider metadata; the model predicts eight categories."
        ),
        "evaluation_note": (
            "Metrics come from a 75/25 stratified split of the project's curated seed "
            "corpus. Because that corpus is small and authored for NewsHub, scores are "
            "indicative and should not be read as real-world benchmark accuracy."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    logger.info("Trained category model: accuracy=%s", metrics["accuracy"])
    return metrics


def load_model() -> Pipeline | None:
    global _model, _model_mtime
    if not MODEL_PATH.exists():
        try:
            train_model()
        except Exception as exc:  # noqa: BLE001 - classifier must never break the API
            logger.warning("Could not train categorization model: %s", exc)
            return None
    try:
        mtime = MODEL_PATH.stat().st_mtime
    except OSError:
        return None
    if _model is None or _model_mtime != mtime:
        _model = joblib.load(MODEL_PATH)
        _model_mtime = mtime
    return _model


def predict_category(text: str) -> tuple[str, float] | tuple[None, float]:
    """Return (label, confidence) or (None, 0.0) when the model is unavailable."""
    text = " ".join((text or "").split())
    if len(text) < 3:
        return None, 0.0
    model = load_model()
    if model is None:
        return None, 0.0
    if not hasattr(model, "classes_"):
        return None, 0.0
    if len(text.split()) < 3:
        return None, 0.0
    probabilities = model.predict_proba([text])[0]
    best_index = int(probabilities.argmax())
    return str(model.classes_[best_index]), float(probabilities[best_index])


def classify_article(title: str, description: str = "", content: str = "") -> dict:
    label, confidence = predict_category(f"{title} {description} {content}".strip())
    return {
        "category": label,
        "confidence": round(confidence, 4),
        "accepted": bool(label and confidence >= MIN_CONFIDENCE),
        "method": "tfidf_logistic_regression",
    }


def get_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {"available": False, "reason": "Model has not been trained yet."}
    try:
        return json.loads(METRICS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"available": False, "reason": "Metrics file could not be read."}


def model_status() -> dict:
    metrics = get_metrics()
    return {
        "available": MODEL_PATH.exists() and bool(metrics.get("available")),
        "artifact": str(MODEL_PATH.name),
        "trained_at": metrics.get("trained_at"),
        "accuracy": metrics.get("accuracy"),
        "macro_f1": metrics.get("macro_f1"),
        "dataset_rows": metrics.get("dataset_rows"),
        "dataset_fingerprint": metrics.get("dataset_fingerprint"),
        "outdated": bool(
            metrics.get("available")
            and metrics.get("dataset_fingerprint") != dataset_fingerprint()
        ),
    }
