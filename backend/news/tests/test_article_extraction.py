from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from news.services.article_extraction import (
    ArticleExtractionError,
    _extract_html,
    _is_public_http_url,
    clean_article_text,
    extract_article_content,
)


LONG_PARAGRAPHS = "\n\n".join([
    "The state government announced a new public transport initiative on Monday. Officials said the programme will connect several districts and improve daily access to essential services.",
    "The transport department said the first phase will begin next month after local authorities complete route surveys. The department will publish a detailed timetable before services start.",
    "Officials said the project includes upgraded bus stops, new passenger information systems and additional services during peak hours. The programme will be reviewed after its first six months.",
    "Local representatives said residents had asked for better connections between smaller towns and district headquarters. Officials said public feedback will be collected through meetings and an online portal.",
    "The government has not yet announced the final operating budget. The transport department said further details will be released after the procurement process is completed.",
])


class ArticleTextCleaningTests(SimpleTestCase):
    def test_removes_placeholder_newsletter_and_duplicate_paragraphs(self):
        text = clean_article_text(
            "Welcome back to TechCrunch Mobility, your hub for transportation. [6,534 chars]\n\n"
            + LONG_PARAGRAPHS
            + "\n\n" + LONG_PARAGRAPHS.split("\n\n")[0]
            + "\n\nSubscribe to our newsletter for updates."
        )
        self.assertNotIn("Welcome back", text)
        self.assertNotIn("6,534 chars", text)
        self.assertNotIn("Subscribe to our newsletter", text)
        self.assertEqual(text.count("The state government announced"), 1)

    def test_rejects_private_and_non_http_urls(self):
        self.assertFalse(_is_public_http_url("http://127.0.0.1/admin"))
        self.assertFalse(_is_public_http_url("http://localhost:8000/"))
        self.assertFalse(_is_public_http_url("file:///etc/passwd"))
        self.assertFalse(_is_public_http_url("https://example.com/article"))

    def test_rejects_unrelated_publisher_page_title(self):
        html = """<!doctype html><html><head><title>Cricket scores and live updates</title></head>
        <body><article>""" + "".join(
            f"<p>{paragraph}</p>" for paragraph in LONG_PARAGRAPHS.split("\n\n")
        ) + """</article></body></html>"""
        with self.assertRaises(ArticleExtractionError):
            _extract_html(
                html,
                "https://publisher.example/news/transport",
                "TDP wins major municipal election in Pulivendula after four decades",
            )

    def test_extracts_article_text_from_structured_page(self):
        html = """<!doctype html><html><head><title>Transport announcement</title>
        <script type='application/ld+json'>
        {"@context":"https://schema.org","@type":"NewsArticle","headline":"Transport announcement",
        "articleBody":"The state government announced a new public transport initiative on Monday. Officials said the programme will connect several districts and improve daily access to essential services. The transport department said the first phase will begin next month after local authorities complete route surveys. The department will publish a detailed timetable before services start. Officials said the project includes upgraded bus stops, new passenger information systems and additional services during peak hours. The programme will be reviewed after its first six months. Local representatives said residents had asked for better connections between smaller towns and district headquarters. Officials said public feedback will be collected through meetings and an online portal. The government has not yet announced the final operating budget. The transport department said further details will be released after procurement is completed."}
        </script></head><body><nav>Home Politics Subscribe</nav><article><h1>Transport announcement</h1>
        <p>Extra paragraph for body validation that is intentionally long enough to avoid looking like a headline.</p>
        </article></body></html>"""
        text, method = _extract_html(html, "https://publisher.example/news/transport")
        self.assertGreaterEqual(len(text.split()), 45)
        self.assertIn(method, {"trafilatura", "beautifulsoup_fallback"})


class ArticleExtractionServiceTests(SimpleTestCase):
    @override_settings(NEWSHUB={
        "ARTICLE_EXTRACTION_ENABLED": True,
        "ARTICLE_EXTRACTION_RESPECT_ROBOTS": True,
        "ARTICLE_EXTRACTION_TIMEOUT": 9,
        "ARTICLE_EXTRACTION_MAX_BYTES": 3145728,
        "ARTICLE_EXTRACTION_CACHE_TTL": 21600,
        "ARTICLE_EXTRACTION_FAILURE_TTL": 600,
        "USER_AGENT": "NewsHubTest/1.0",
    })
    @patch("news.services.article_extraction.cache.get", return_value=None)
    @patch("news.services.article_extraction.cache.set")
    @patch("news.services.article_extraction._is_public_http_url", return_value=True)
    @patch("news.services.article_extraction._robots_allowed", return_value=(True, ""))
    @patch("news.services.article_extraction._download_html")
    def test_extracts_public_article_and_returns_full_status(
        self, download_html, _robots, _safe, _cache_set, _cache_get
    ):
        article = SimpleNamespace(
            pk=55,
            title="Transport initiative announced",
            description="A brief publisher description.",
            content="",
            source_url="https://publisher.example/news/transport",
        )
        download_html.return_value = (
            "<html><head><title>Transport announcement</title></head><body><article>"
            + "".join(f"<p>{p}</p>" for p in LONG_PARAGRAPHS.split("\n\n"))
            + "</article></body></html>",
            article.source_url,
        )
        result = extract_article_content(article)
        self.assertEqual(result.content_status, "full")
        self.assertEqual(result.content_source, "publisher_page")
        self.assertGreaterEqual(result.word_count, 120)
        self.assertTrue(result.text)

    @override_settings(NEWSHUB={
        "ARTICLE_EXTRACTION_ENABLED": True,
        "ARTICLE_EXTRACTION_RESPECT_ROBOTS": True,
        "ARTICLE_EXTRACTION_FAILURE_TTL": 600,
        "USER_AGENT": "NewsHubTest/1.0",
    })
    @patch("news.services.article_extraction.cache.get", return_value=None)
    @patch("news.services.article_extraction.cache.set")
    @patch("news.services.article_extraction._is_public_http_url", return_value=True)
    @patch("news.services.article_extraction._robots_allowed", return_value=(False, "robots disallow"))
    def test_robots_restriction_falls_back_to_feed_text(self, *_mocks):
        article = SimpleNamespace(
            pk=56,
            title="Local transport update",
            description="Only a short publisher description is available here.",
            content="",
            source_url="https://publisher.example/news/restricted",
        )
        result = extract_article_content(article)
        self.assertEqual(result.content_status, "headline_only")
        self.assertEqual(result.content_source, "description")
        self.assertIn("robots disallow", result.note)
