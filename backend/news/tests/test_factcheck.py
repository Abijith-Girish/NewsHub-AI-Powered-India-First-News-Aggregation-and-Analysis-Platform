from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import FactCheck
from news.providers.base import NormalizedArticle, ProviderResult
from news.tests.factories import make_article, make_user

CLAIM = "The central bank raised interest rates to nine percent"


def evidence(title, description, url, source="Reuters"):
    return NormalizedArticle(
        title=title,
        description=description,
        source_url=url,
        source_name=source,
        published_at=timezone.now(),
    )


def provider_result(items, succeeded=1):
    return ProviderResult(
        articles=items, providers_attempted=1, providers_succeeded=succeeded
    )


@patch("news.services.factcheck.is_llm_enabled", lambda: False)
class FactCheckTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    @patch("news.services.factcheck.search_external")
    def test_contradicted_by_multiple_sources(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "Fact check: central bank did not raise interest rates to nine percent",
                    "Claims that the bank raised interest rates to nine percent are false, "
                    "according to the official statement.",
                    "https://www.snopes.com/fact-check/rates-false/",
                    "Snopes",
                ),
                evidence(
                    "Central bank denies interest rate claim",
                    "The bank denies raising interest rates to nine percent and calls the "
                    "report misleading.",
                    "https://www.reuters.com/world/bo-denies/",
                    "Reuters",
                ),
            ]
        )
        response = self.client.post(
            "/api/fact-check/", {"claim": CLAIM}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.CONTRADICTED)
        self.assertTrue(data["evidence"])
        self.assertTrue(all(item["url"].startswith("https://") for item in data["evidence"]))
        self.assertIn("not a definitive verdict", data["disclaimer"])
        self.assertGreaterEqual(data["analysis_notes"]["providers_succeeded"], 1)
        self.assertTrue(data["analysis_notes"]["queries"])
        record = FactCheck.objects.get(reference=data["id"])
        self.assertEqual(record.verdict, FactCheck.Verdict.CONTRADICTED)

    @patch("news.services.factcheck.search_external")
    def test_supported_by_confirming_language(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "Central bank confirms interest rate rise to nine percent",
                    "The central bank confirmed it raised interest rates to nine percent, "
                    "according to the official statement.",
                    "https://www.bbc.com/news/central-bank-confirms",
                    "BBC News",
                ),
                evidence(
                    "Interest rates raised to nine percent by central bank",
                    "Officials confirmed the interest rate increase to nine percent at the "
                    "policy meeting, data shows.",
                    "https://apnews.com/article/central-bank-rates",
                    "Associated Press",
                ),
            ]
        )
        data = self.client.post("/api/fact-check/", {"claim": CLAIM}, format="json").json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.SUPPORTED)
        self.assertGreater(data["confidence"], 0.3)
        self.assertIn("not independent proof", data["explanation"])

    @patch("news.services.factcheck.search_external")
    def test_direct_high_coverage_reporting_supports_claim(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "Brewers beat Rays in Game 1 of the World Series",
                    "Milwaukee won the opener against Tampa Bay in the World Series.",
                    "https://www.espn.com/sports/game-one-recap",
                    "ESPN",
                ),
                evidence(
                    "World Series Game 1: Brewers defeat Rays",
                    "The Brewers took Game 1 of the World Series from the Rays.",
                    "https://www.reuters.com/sports/world-series-game-one/",
                    "Reuters",
                ),
            ]
        )
        data = self.client.post(
            "/api/fact-check/",
            {"claim": "The Brewers beat the Rays in Game 1 of the World Series"},
            format="json",
        ).json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.SUPPORTED)

    @patch("news.services.factcheck.search_external")
    def test_unknown_sources_cannot_produce_a_verdict(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "NASA confirms that the Earth is flat",
                    "A blog says NASA confirmed the Earth is flat and hides the evidence.",
                    "https://truthblog.example.com/flat-earth",
                    "Truth Blog",
                ),
                evidence(
                    "Earth is flat, NASA confirmation leaked",
                    "Alternative media reports that NASA confirmed the Earth is flat.",
                    "https://altwire.example.com/nasa-flat",
                    "Alternative Wire",
                ),
            ]
        )
        data = self.client.post(
            "/api/fact-check/",
            {"claim": "NASA confirmed that the Earth is flat"},
            format="json",
        ).json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.INSUFFICIENT)
        self.assertFalse(any(item["trusted"] for item in data["evidence"]))

    @patch("news.services.factcheck.search_external")
    def test_relevant_conflict_is_mixed_even_if_one_source_is_not_allowlisted(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "Central bank confirms interest rate rise to nine percent",
                    "The central bank confirmed that it raised interest rates to nine percent.",
                    "https://www.reuters.com/markets/central-bank-rates/",
                    "Reuters",
                ),
                evidence(
                    "Central bank did not raise interest rates to nine percent",
                    "The central bank did not raise interest rates to nine percent, according to the document.",
                    "https://localexample.invalid/central-bank-claim/",
                    "Local Example",
                ),
            ]
        )
        data = self.client.post("/api/fact-check/", {"claim": CLAIM}, format="json").json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.MIXED)
        self.assertEqual(data["analysis_notes"]["supporting_items"], 1)
        self.assertEqual(data["analysis_notes"]["contradicting_items"], 1)

    @patch("news.services.factcheck.search_external")
    def test_single_ordinary_publisher_is_not_enough_for_supported_verdict(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "Central bank confirms interest rate rise to nine percent",
                    "The central bank confirmed it raised interest rates to nine percent.",
                    "https://www.reuters.com/markets/central-bank-rates/",
                    "Reuters",
                ),
            ]
        )
        data = self.client.post("/api/fact-check/", {"claim": CLAIM}, format="json").json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.INSUFFICIENT)

    @patch("news.services.factcheck.search_external")
    def test_unrelated_contract_story_is_not_returned_as_evidence(self, search_external):
        search_external.return_value = provider_result(
            [
                evidence(
                    "NBA Contract Year: Grizzlies' Ty Jerome and 11 others playing for a payday",
                    "Several basketball players enter a contract year ahead of the season.",
                    "https://www.espn.com/nba/story/contract-year",
                    "ESPN",
                ),
            ]
        )
        claim = "Inside C.J. Stroud's high-stakes decision not to sign a contract extension"
        data = self.client.post("/api/fact-check/", {"claim": claim}, format="json").json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.INSUFFICIENT)
        self.assertEqual(data["evidence"], [])

    @patch("news.services.factcheck.search_external")
    def test_no_evidence_returns_insufficient(self, search_external):
        search_external.return_value = provider_result([], succeeded=0)
        data = self.client.post(
            "/api/fact-check/", {"claim": "A completely unverifiable local rumour"}, format="json"
        ).json()
        self.assertEqual(data["verdict"], FactCheck.Verdict.INSUFFICIENT)
        self.assertEqual(data["evidence"], [])
        self.assertIn("not enough to assess", data["explanation"])
        self.assertTrue(data["analysis_notes"]["limitations"])

    def test_requires_some_input(self):
        response = self.client.post("/api/fact-check/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_url(self):
        response = self.client.post(
            "/api/fact-check/", {"claim": "x", "source_url": "not-a-url"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    @patch("news.services.factcheck.search_external")
    def test_detail_is_private_to_owner(self, search_external):
        search_external.return_value = provider_result([])
        owner = make_user("owner")
        other = make_user("other")
        self.client.force_authenticate(user=owner)
        created = self.client.post(
            "/api/fact-check/", {"claim": "Claim submitted by the owner"}, format="json"
        ).json()
        reference = created["id"]

        self.client.force_authenticate(user=other)
        self.assertEqual(
            self.client.get(f"/api/fact-check/{reference}/").status_code, 404
        )
        self.client.force_authenticate(user=owner)
        self.assertEqual(
            self.client.get(f"/api/fact-check/{reference}/").status_code, 200
        )

    def test_history_requires_authentication(self):
        self.assertEqual(self.client.get("/api/fact-check/history/").status_code, 401)

    @patch("news.services.factcheck.search_external")
    def test_related_stored_articles_are_linked(self, search_external):
        search_external.return_value = provider_result([])
        make_article(
            "Central bank raises interest rates to nine percent",
            category_slug="business",
        )
        data = self.client.post("/api/fact-check/", {"claim": CLAIM}, format="json").json()
        self.assertTrue(data["related_articles"])
        self.assertTrue(data["related_articles"][0]["url"].startswith("https://"))
