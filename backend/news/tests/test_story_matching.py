from django.test import TestCase
from django.utils import timezone

from news.ml.story_matching import find_claim_matches, find_story_matches
from news.tests.factories import make_article


class NewsLensMatchingTests(TestCase):
    def test_paraphrased_same_event_is_matched_across_publishers(self):
        anchor = make_article(
            "Supreme Court Stops Salary Of Mumbai Corporation Commissioner Over Failure To Remove Encroachments",
            description="The court directed the civic body to act on illegal encroachments in Mumbai.",
            source_name="Live Law",
            source_url="https://www.livelaw.in/story/supreme-court-mumbai-salary",
            published_at=timezone.now(),
        )
        candidate = make_article(
            "Why did Supreme Court freeze Mumbai civic commissioner's salary and impose fine on BMC?",
            description="The Supreme Court paused the municipal chief's pay over the failure to clear encroachments.",
            source_name="Mint",
            source_url="https://www.livemint.com/news/india/mumbai-bmc-commissioner-salary",
            published_at=timezone.now(),
        )
        matches = find_story_matches(anchor)
        ids = [item["article"].id for item in matches]
        self.assertIn(candidate.id, ids)
        matched = next(item for item in matches if item["article"].id == candidate.id)
        self.assertGreaterEqual(matched["similarity"], 0.22)
        self.assertTrue(matched["shared_event_terms"])

    def test_same_city_and_institution_but_different_event_is_not_matched(self):
        anchor = make_article(
            "Supreme Court Stops Salary Of Mumbai Corporation Commissioner Over Failure To Remove Encroachments",
            description="The court directed the civic body to act on illegal encroachments in Mumbai.",
            source_name="Live Law",
            source_url="https://www.livelaw.in/story/supreme-court-mumbai-salary",
        )
        unrelated = make_article(
            "Supreme Court asks Mumbai civic body to improve monsoon drainage",
            description="The court heard a petition about flooded roads and stormwater drains in Mumbai.",
            source_name="NDTV",
            source_url="https://www.ndtv.com/mumbai/drainage-case",
        )
        matches = find_story_matches(anchor)
        self.assertNotIn(unrelated.id, [item["article"].id for item in matches])


class TruthTraceMatchingTests(TestCase):
    def test_broad_keyword_only_match_is_rejected(self):
        claim = "Inside C.J. Stroud's high-stakes decision not to sign a contract extension"
        unrelated = make_article(
            "NBA Contract Year: Grizzlies' Ty Jerome and 11 others playing for a payday",
            description="Several basketball players enter a contract year ahead of the season.",
            source_name="ESPN",
            source_url="https://www.espn.com/nba/story/contract-year",
        )
        self.assertEqual(find_claim_matches(claim, [unrelated]), [])

    def test_claim_match_requires_specific_overlap(self):
        claim = "The central bank raised interest rates to nine percent"
        unrelated = make_article(
            "Central bank announces new office hours",
            description="The bank changed its customer service opening hours.",
            source_name="Example News",
            source_url="https://example.com/bank-hours",
        )
        related = make_article(
            "Central bank confirms interest rate rise to nine percent",
            description="Officials confirmed the benchmark interest rate was raised to nine percent.",
            source_name="Reuters",
            source_url="https://www.reuters.com/markets/rates-rise",
        )
        matches = find_claim_matches(claim, [unrelated, related])
        ids = [item["article"].id for item in matches]
        self.assertIn(related.id, ids)
        self.assertNotIn(unrelated.id, ids)
