"""Curated, publicly available RSS feeds used by the aggregator.

Every entry declares the NewsHub category it maps to. Feeds are fetched on the
server only; the browser never talks to these providers directly. Adding or
removing a source is a one-line change and needs no other code edits.

All listed endpoints are public RSS/Atom feeds that publishers offer for
syndication. The aggregator stores only headline, short description, image and
link, and always links back to the publisher.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedConfig:
    key: str
    name: str
    url: str
    category: str
    breaking_source: bool = False


GOOGLE = "https://news.google.com/rss"
GOOGLE_HL = "en-IN"
GOOGLE_GL = "IN"
GOOGLE_CEID = "IN:en"
GOOGLE_REGION = f"hl={GOOGLE_HL}&gl={GOOGLE_GL}&ceid={GOOGLE_CEID}"
GOOGLE_TOPIC = f"{GOOGLE}/headlines/section/topic/{{topic}}?{GOOGLE_REGION}"
GOOGLE_SEARCH = f"{GOOGLE}/search?q={{query}}&{GOOGLE_REGION}"


def _google_topic(topic: str) -> str:
    return GOOGLE_TOPIC.format(topic=topic)


def _google_search(query: str) -> str:
    from urllib.parse import quote_plus
    return GOOGLE_SEARCH.format(query=quote_plus(query))


# India-first source mix with international coverage retained. Google News
# site-restricted feeds are used for publishers whose syndication terms or feed
# availability make direct feed ingestion inappropriate.
FEEDS: list[FeedConfig] = [
    # --- India edition: Google News ---------------------------------------
    FeedConfig("google_top", "Google News India", f"{GOOGLE}?{GOOGLE_REGION}", "world", True),
    FeedConfig("google_india", "Google News India", _google_search("India OR Indian"), "politics", True),
    FeedConfig("google_technology", "Google News Technology India", _google_topic("TECHNOLOGY"), "technology"),
    FeedConfig("google_ai", "Google News AI India", _google_search('artificial intelligence OR "machine learning"'), "artificial-intelligence"),
    FeedConfig("google_business", "Google News Business India", _google_topic("BUSINESS"), "business"),
    FeedConfig("google_politics", "Google News Politics India", _google_topic("NATION"), "politics"),
    FeedConfig("google_sports", "Google News Sports India", _google_topic("SPORTS"), "sports"),
    FeedConfig("google_entertainment", "Google News Entertainment India", _google_topic("ENTERTAINMENT"), "entertainment"),
    FeedConfig("google_health", "Google News Health India", _google_topic("HEALTH"), "health"),
    FeedConfig("google_science", "Google News Science India", _google_topic("SCIENCE"), "science"),
    FeedConfig("google_world", "Google News World India edition", _google_search("world international news"), "world"),
    FeedConfig("google_toi", "The Times of India (via Google News)", _google_search("site:timesofindia.indiatimes.com"), "world"),
    FeedConfig("google_wion", "WION (via Google News)", _google_search("site:wionews.com"), "world"),
    FeedConfig("google_news18", "News18 (via Google News)", _google_search("site:news18.com India news"), "world"),
    FeedConfig("google_deccan_herald", "Deccan Herald (via Google News)", _google_search("site:deccanherald.com India news"), "politics"),
    FeedConfig("google_firstpost", "Firstpost (via Google News)", _google_search("site:firstpost.com India news"), "world"),
    FeedConfig("google_scroll", "Scroll.in (via Google News)", _google_search("site:scroll.in India news"), "politics"),
    FeedConfig("google_the_print", "The Print (via Google News)", _google_search("site:theprint.in India news"), "politics"),
    # --- Indian publishers: RSS feeds ------------------------------------
    FeedConfig("the_hindu", "The Hindu", "https://www.thehindu.com/feeder/default.rss", "world", True),
    FeedConfig("the_hindu_national", "The Hindu India", "https://www.thehindu.com/news/national/feeder/default.rss", "politics"),
    FeedConfig("ndtv", "NDTV", "https://feeds.feedburner.com/ndtvnews-top-stories", "world", True),
    FeedConfig("hindustan_times", "Hindustan Times", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "politics"),
    FeedConfig("indian_express", "The Indian Express", "https://indianexpress.com/feed/", "world"),
    FeedConfig("india_today", "India Today", "https://www.indiatoday.in/rss/home", "world"),
    FeedConfig("mint", "Mint", "https://www.livemint.com/rss/news", "business"),
    FeedConfig("business_standard", "Business Standard", "https://www.business-standard.com/rss/home_page_top_stories.rss", "business"),
    FeedConfig("economic_times", "The Economic Times", "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "business"),
    # --- International publishers ----------------------------------------
    FeedConfig("bbc_world", "BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml", "world", True),
    FeedConfig("bbc_india", "BBC News India", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml", "politics"),
    FeedConfig("guardian_world", "The Guardian", "https://www.theguardian.com/world/rss", "world"),
    FeedConfig("guardian_business", "The Guardian Business", "https://www.theguardian.com/business/rss", "business"),
    FeedConfig("guardian_science", "The Guardian Science", "https://www.theguardian.com/science/rss", "science"),
    FeedConfig("guardian_education", "The Guardian Education", "https://www.theguardian.com/education/rss", "education"),
    FeedConfig("aljazeera", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "world"),
    FeedConfig("dw_world", "Deutsche Welle", "https://rss.dw.com/rdf/rss-en-all", "world"),
    FeedConfig("npr", "NPR", "https://feeds.npr.org/1001/rss.xml", "world"),
    # --- Specialist coverage ---------------------------------------------
    FeedConfig("techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "technology"),
    FeedConfig("the_verge", "The Verge", "https://www.theverge.com/rss/index.xml", "technology"),
    FeedConfig("arstechnica", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "technology"),
    FeedConfig("wired", "WIRED", "https://www.wired.com/feed/rss", "technology"),
    FeedConfig("mit_tech_review", "MIT Technology Review", "https://www.technologyreview.com/feed/", "technology"),
    FeedConfig("espn", "ESPN", "https://www.espn.com/espn/rss/news", "sports"),
    FeedConfig("hollywood_reporter", "The Hollywood Reporter", "https://www.hollywoodreporter.com/feed/", "entertainment"),
    FeedConfig("variety", "Variety", "https://variety.com/feed/", "entertainment"),
    FeedConfig("nature", "Nature", "https://www.nature.com/nature.rss", "science"),
    FeedConfig("statnews", "STAT News", "https://www.statnews.com/feed/", "health"),
    FeedConfig("edsurge", "EdSurge", "https://www.edsurge.com/articles_rss", "education"),
]

FEEDS_BY_KEY = {feed.key: feed for feed in FEEDS}
FEED_KEYS = [feed.key for feed in FEEDS]

# The normal homepage refresh deliberately covers India and world sources.
# A full refresh (`ingest_news --all`) fetches every configured feed.
BALANCED_FEEDS = [
    "google_top", "google_india", "google_technology", "google_business",
    "google_politics", "google_sports", "google_world", "google_toi", "google_wion",
    "google_news18", "google_deccan_herald", "google_firstpost", "google_scroll", "google_the_print",
    "the_hindu", "the_hindu_national", "ndtv", "hindustan_times", "indian_express",
    "india_today", "mint", "business_standard", "economic_times",
    "bbc_world", "bbc_india", "guardian_world", "aljazeera", "dw_world",
    "techcrunch", "espn", "nature",
]

CATEGORY_SLUGS = [
    "technology",
    "artificial-intelligence",
    "politics",
    "business",
    "sports",
    "entertainment",
    "health",
    "education",
    "science",
    "world",
]

CATEGORY_METADATA = {
    "technology": {
        "name": "Technology",
        "description": "Consumer tech, software, startups and the companies shaping the industry.",
        "keywords": "software, app, gadget, chip, smartphone, startup, cloud, computing, internet, tech company",
        "order": 1,
    },
    "artificial-intelligence": {
        "name": "Artificial Intelligence",
        "description": "Machine learning research, AI products, models and policy.",
        "keywords": "artificial intelligence, machine learning, ai model, llm, neural network, chatbot, deep learning, generative ai",
        "order": 2,
    },
    "politics": {
        "name": "Politics",
        "description": "Elections, legislation, governance and policy debates.",
        "keywords": "election, parliament, government, senator, congress, policy, minister, president, vote, legislation",
        "order": 3,
    },
    "business": {
        "name": "Business",
        "description": "Markets, economy, earnings and corporate news.",
        "keywords": "market, economy, earnings, company, stocks, inflation, revenue, merger, trade, investor",
        "order": 4,
    },
    "sports": {
        "name": "Sports",
        "description": "Matches, leagues, transfers and athletes.",
        "keywords": "match, league, team, coach, tournament, football, cricket, basketball, athlete, championship",
        "order": 5,
    },
    "entertainment": {
        "name": "Entertainment",
        "description": "Film, television, music, streaming and celebrity news.",
        "keywords": "film, movie, series, streaming, actor, music, album, box office, director, television",
        "order": 6,
    },
    "health": {
        "name": "Health",
        "description": "Medicine, public health, research and wellbeing.",
        "keywords": "health, hospital, disease, vaccine, medicine, patient, clinical, virus, treatment, mental health",
        "order": 7,
    },
    "education": {
        "name": "Education",
        "description": "Universities, schools, students and education policy.",
        "keywords": "education, university, school, student, teacher, college, exam, curriculum, campus, learning",
        "order": 8,
    },
    "science": {
        "name": "Science",
        "description": "Research, space, climate and scientific discovery.",
        "keywords": "research, study, scientists, space, climate, physics, biology, discovery, nasa, experiment",
        "order": 9,
    },
    "world": {
        "name": "World News",
        "description": "International affairs and global reporting.",
        "keywords": "world, international, global, foreign, conflict, diplomats, united nations, crisis, border, summit",
        "order": 10,
    },
}
