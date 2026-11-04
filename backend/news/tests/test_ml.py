from django.test import TestCase
from rest_framework.test import APIClient

from news.ml.classifier import LABELS, classify_article, get_metrics, predict_category
from news.ml.sentiment import analyze_sentiment
from news.ml.summarizer import summarize_article
from news.tests.factories import make_article


class ClassifierTests(TestCase):
    def test_model_is_trained_and_predicts_known_categories(self):
        cases = {
            "Senate passes election reform bill after late debate": "politics",
            "Star striker scores twice as the league leaders win": "sports",
            "Hospital expands mental health services for patients": "health",
            "Researchers find water vapour on a distant exoplanet": "science",
        }
        for text, expected in cases.items():
            label, confidence = predict_category(text)
            self.assertIn(label, LABELS)
            self.assertGreater(confidence, 0)
            self.assertEqual(label, expected, msg=f"unexpected label for: {text}")

    def test_classification_rejects_empty_text(self):
        result = classify_article("")
        self.assertIsNone(result["category"])
        self.assertFalse(result["accepted"])

    def test_metrics_are_real_and_complete(self):
        metrics = get_metrics()
        self.assertTrue(metrics["available"])
        for key in ("accuracy", "macro_f1", "per_class", "confusion_matrix", "test_rows"):
            self.assertIn(key, metrics)
        self.assertGreater(metrics["test_rows"], 0)
        self.assertLessEqual(metrics["accuracy"], 1.0)
        matrix = metrics["confusion_matrix"]["matrix"]
        self.assertEqual(len(matrix), len(metrics["confusion_matrix"]["labels"]))


class SentimentTests(TestCase):
    def test_positive_negative_neutral(self):
        self.assertEqual(
            analyze_sentiment("The company reports record profits and strong growth")["label"],
            "positive",
        )
        self.assertEqual(
            analyze_sentiment("Major losses and layoffs hit the struggling firm")["label"],
            "negative",
        )
        self.assertEqual(
            analyze_sentiment("The meeting is scheduled for Tuesday morning")["label"],
            "neutral",
        )

    def test_empty_text_is_neutral_with_note(self):
        result = analyze_sentiment("")
        self.assertEqual(result["label"], "neutral")
        self.assertIn("No text", result["explanation"])

    def test_sentiment_endpoint_returns_disclaimer(self):
        client = APIClient()
        response = client.post(
            "/api/ai/sentiment/", {"text": "The team celebrated a major win."}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["label"], "positive")
        self.assertIn("disclaimer", response.json())


class SummarizerTests(TestCase):
    def test_extractive_summary_uses_available_content(self):
        content = (
            "The city council approved a new transit plan on Tuesday. "
            "The plan adds twelve kilometres of protected bus lanes. "
            "Construction will begin next spring and take two years. "
            "Officials said fares would stay unchanged during the work. "
            "Local businesses welcomed the investment in public transport. "
            "Opponents argued the project should have included rail service."
        )
        article = make_article("Council approves transit plan", content=content)
        # The test article is a short body excerpt, so NewsHub must label it
        # partial rather than claiming it has the full publisher article.
        from unittest.mock import patch
        with patch("news.ml.summarizer.is_llm_enabled", return_value=False):
            result = summarize_article(article, "short")
        self.assertEqual(result["method"], "extractive_tfidf")
        self.assertTrue(result["limited_content"])
        self.assertEqual(result["content_status"], "partial")
        self.assertIn("publisher_feed", result["based_on"])
        self.assertLessEqual(result["word_count"], 70)
        self.assertTrue(result["summary"])
        self.assertIn("disclaimer", result)

    def test_summary_without_content_is_flagged_limited(self):
        article = make_article(
            "Parliament approves budget",
            description="Lawmakers voted after a long debate on housing funding.",
            content="",
        )
        result = summarize_article(article, "detailed")
        self.assertTrue(result["limited_content"])
        self.assertTrue(result["warning"])
        self.assertIn("description", result["based_on"])

    def test_summarize_endpoint_by_article_id(self):
        article = make_article(
            "Company reports quarterly results",
            description="Revenue rose while costs fell.",
            content=" ".join(["Revenue increased by ten percent this quarter."] * 12),
        )
        response = APIClient().post(
            "/api/ai/summarize/", {"article_id": article.id, "length": "detailed"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["article_id"], article.id)
        self.assertGreater(response.json()["word_count"], 0)

    def test_summarize_endpoint_validates_input(self):
        response = APIClient().post("/api/ai/summarize/", {}, format="json")
        self.assertEqual(response.status_code, 400)


class MlEndpointTests(TestCase):
    def test_categorize_endpoint(self):
        response = APIClient().post(
            "/api/ml/categorize/",
            {"title": "Central bank raises interest rates", "description": "Markets fell after the decision."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["category"], LABELS)
        self.assertIn("confidence", data)
        self.assertTrue(data["model"]["available"])

    def test_metrics_endpoint_matches_artifact(self):
        response = APIClient().get("/api/ml/metrics/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["model"]["available"])
        self.assertEqual(data["metrics"]["accuracy"], get_metrics()["accuracy"])
