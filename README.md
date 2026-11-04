# NewsHub — AI-powered news aggregation and analysis

NewsHub is a full-stack news platform. It pulls real headlines from multiple
publishers, de-duplicates them, classifies every story with a locally trained
machine-learning model, and adds clearly-labelled AI analysis: summaries,
sentiment, personalized recommendations, related-article search and an
evidence-based claim check.

The application is built rather than mocked: the Django API writes real
articles into SQLite, the React client reads them over HTTP, and the classifier
is trained and evaluated in this repository.

---

## 1. What works (and what does not pretend to work)

| Area | Status |
|---|---|
| Live aggregation from RSS / Google News (no API key required) | ✅ 47 curated feeds (31 in normal refresh), India-first Google News edition, parallel fetch, 8s timeouts |
| Deduplication | ✅ canonical URLs, tracking-parameter stripping, same-publisher near-duplicate detection; alternate publishers are retained |
| Topic search across providers | ✅ Google News search + optional NewsAPI/GNews, stored and ranked with TF-IDF |
| Category browsing and automatic categorization | ✅ TF-IDF + logistic regression, confidence stored, editor override |
| Trending topics | ✅ derived from stored headline frequency, real counts only |
| Content-based recommendations | ✅ cosine similarity + recency, per-article and per-user |
| Registration / login / logout | ✅ DRF token auth, Django password hashing, throttled |
| Saved articles, interests, personalization | ✅ server-side, scoped to the signed-in user |
| AI summaries | ✅ Gemini primary → Groq fallback; local extractive fallback; content completeness is disclosed |
| Sentiment | ✅ pretrained VADER lexicon, explicit "tone only" disclaimer |
| Fact check | ✅ conservative evidence retrieval and scoring; returns “insufficient evidence” when appropriate |
| Admin dashboard | ✅ article CRUD, ML review queue, categories, users, provider status |
| Automated tests | ✅ Backend regression tests included; run with `python manage.py test` |
| Fake-news *detector* | ❌ not claimed. No labelled fake-news dataset was trained or evaluated. |

Important limitations are repeated where they matter in the UI and in
[section 10](#10-fact-check-methodology-honest-limits).

### Publisher article text extraction

When an article feed contains only a headline or short description, NewsHub can
attempt on-demand extraction from the stored publisher URL. Trafilatura is used
first, with structured-data and BeautifulSoup fallbacks. Extraction is bounded by
request timeouts and response-size limits, validates public HTTP(S) destinations
and redirects, and respects publisher `robots.txt`, access-denied responses,
paywalls, login walls and CAPTCHA pages. It does not bypass publisher controls.

The extraction endpoint is `GET /api/news/<article_id>/content/`. The article
reader offers a **Load available article text** action. Summarization and
translation use the same cached extraction result. Extracted article text is held
in the application cache temporarily and is not written back to the Article table.
The API reports `full`, `partial` or `headline_only` so generated output does not
claim to represent content that NewsHub could not retrieve. Publisher restrictions
or JavaScript-only pages may still prevent extraction; the original publisher link
remains authoritative.

---

## 2. Architecture

```
React 18 + Vite + Tailwind (port 3000)
        │  Axios, token auth, same-origin /api proxy
        ▼
Django REST Framework (port 8000)
        ├── news/providers     RSS + Google News + optional NewsAPI/GNews
        ├── news/services      aggregation, dedupe, categorization, fact check
        ├── news/ml            classifier, sentiment, recommendations, summarizer
        └── accounts           auth, preferences
        ▼
SQLite (Django ORM; PostgreSQL-ready)
```

The browser never contacts news providers and never sees an API key. All
external requests, analysis and persistence happen on the Django side. Dates
and generated timestamps are presented in the `Asia/Kolkata` time zone.

---

## 3. Technology

**Frontend:** React 18, Vite 5, Tailwind CSS 3, React Router 6, Axios, Lucide icons.

**Backend:** Python 3.12, Django 5.2, Django REST Framework, django-cors-headers,
feedparser, requests, BeautifulSoup.

**ML / NLP:** scikit-learn (TF-IDF, Logistic Regression, cosine similarity),
pandas, NumPy, joblib, VADER sentiment, Trafilatura and BeautifulSoup article extraction.

**Storage:** SQLite during development; no database-specific SQL is used.

**Optional AI:** Gemini is the primary chat-completions provider, Groq is the fallback, and Sarvam handles Indian-language translation. Keys are server-side in `backend/.env`. The local extractive summarizer remains available if both AI providers fail.

---

## 4. Repository layout

```
.
├── backend/
│   ├── config/                 Django settings, root URLs, WSGI/ASGI
│   ├── accounts/               registration, login, profile, preferences
│   ├── news/
│   │   ├── feeds.py            curated feed list (add sources here)
│   │   ├── models.py           Category, Article, SavedArticle, Interaction, FactCheck
│   │   ├── providers/          RSS + Google News + optional JSON APIs
│   │   ├── services/
│   │   │   ├── aggregator.py   fetch → normalize → dedupe → categorize → store
│   │   │   ├── dedupe.py       URL/title normalization
│   │   │   ├── categorization.py
│   │   │   ├── trending.py
│   │   │   ├── factcheck.py    evidence retrieval + stance scoring
│   │   │   └── llm.py          optional OpenAI-compatible client
│   │   ├── ml/
│   │   │   ├── data/training_data.csv   curated seed corpus (324 rows)
│   │   │   ├── classifier.py            train / evaluate / predict
│   │   │   ├── recommend.py             TF-IDF cosine recommendations
│   │   │   ├── sentiment.py             VADER + fallback
│   │   │   └── summarizer.py            extractive + optional LLM
│   │   ├── management/commands/         seed_categories, train_classifier,
│   │   │                                ingest_news, reclassify_articles
│   │   ├── tests/                       74 API/ML/aggregation tests
│   │   └── admin_views.py, ai_views.py, views.py, serializers.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/         navbar, cards, filters, skeletons, AI panels…
│   │   ├── pages/              home, explore, article, fact-check, saved, profile, admin
│   │   ├── context/            auth + theme providers
│   │   ├── hooks/              useFetch, useDocumentTitle
│   │   └── lib/                axios client, formatting, toast events
│   ├── vite.config.js          /api proxy + dev host allowlist
│   └── package.json
└── README.md
```

---

## 5. Quick start

### Prerequisites

- Python 3.11+ (tested on 3.12)
- Node.js 18+ (tested on 24)
- Network access for live news. The app still runs without it, but feeds will
  be empty and the UI shows an honest error state.

### 5.1 Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # optional for local defaults; edit as needed

python manage.py migrate
python manage.py seed_categories
python manage.py train_classifier  # trains + prints evaluation metrics
python manage.py ingest_news --all # pulls real articles from configured feeds
python manage.py createsuperuser   # needed to use the admin dashboard
python manage.py runserver 0.0.0.0:8000
```

Check it:

```bash
curl http://127.0.0.1:8000/api/health/
curl "http://127.0.0.1:8000/api/news/?page_size=3"
```

### 5.2 Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Vite proxies `/api` to Django, so no CORS
configuration is needed in development.

If you serve the dev server through another hostname (a preview domain), pass
it explicitly instead of weakening host checks:

```bash
VITE_ALLOWED_HOSTS=preview.example.com npm run dev
```

Production build: `npm run build` (output in `frontend/dist`).

### 5.3 Daily ingestion (optional)

For a long-running deployment, refresh feeds on a schedule instead of relying
on request-driven freshness checks:

```bash
# cron: every 20 minutes
*/20 * * * * cd /srv/newshub/backend && .venv/bin/python manage.py ingest_news --all >> /var/log/newshub-ingest.log 2>&1
```

---

## 6. Configuration

All backend secrets live in `backend/.env` (git-ignored). Copy
`backend/.env.example` to start.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | **Set a long random value in production** |
| `DJANGO_DEBUG` | `true` | Set `false` in production |
| `DJANGO_ALLOWED_HOSTS` | localhost… | Comma-separated hostnames |
| `DJANGO_CORS_ALLOWED_ORIGINS` | localhost:3000/5173 | Direct-origin API clients |
| `NEWS_FETCH_TIMEOUT` | `8` | Per-feed HTTP timeout (seconds) |
| `NEWS_CACHE_TTL` | `600` | Provider/search cache seconds |
| `NEWS_MAX_ARTICLES_PER_FEED` | `35` | Items read per feed per refresh |
| `NEWS_MAX_FEEDS` | `50` | Maximum configured feeds fetched in a full refresh (47 are currently configured) |
| `NEWS_FRESHNESS_MINUTES` | `15` | Minimum gap between automatic refreshes |
| `NEWS_ENABLE_LIVE_FETCH` | `true` | Turn off to run entirely from stored articles |
| `NEWSAPI_KEY` | empty | Optional; enables NewsAPI as an extra provider |
| `GNEWS_API_KEY` | empty | Optional; enables GNews |
| `LLM_API_KEY` | empty | Optional; enables abstractive summaries, LLM translation fallback and generated briefings |
| `SARVAM_API_KEY` | empty | Enables Sarvam Translate for Hindi, Malayalam, Tamil, Telugu and Kannada |
| `SARVAM_TRANSLATE_API_URL` | `https://api.sarvam.ai/translate` | Sarvam Indian-language translation endpoint |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for the endpoint |
| `TRANSLATION_API_URL` | empty | Optional LibreTranslate `/translate` endpoint; Sarvam is preferred when its key is present |
| `TRANSLATION_API_KEY` | empty | Optional key for a managed LibreTranslate host |
| `TRANSLATION_TIMEOUT` | `25` | Translation request timeout in seconds |

The frontend needs no secrets. See `frontend/.env.example` for optional dev
host/proxy settings.

### Translation setup

NewsHub supports the Sarvam Translate API for Hindi, Malayalam, Tamil, Telugu
and Kannada. Set `SARVAM_API_KEY` in `backend/.env` (or the root `.env` for
Docker Compose). The API key is never sent to the browser. Sarvam's text
translation endpoint limits each request to 2,000 characters; NewsHub splits
longer article text into smaller chunks and caches successful translations.
See the [Sarvam Translate API reference](https://docs.sarvam.ai/api-reference/text/translate-text).

Alternatively configure `TRANSLATION_API_URL` for a self-hosted or managed
LibreTranslate-compatible `/translate` endpoint, or set `LLM_API_KEY` to enable
the OpenAI-compatible translation fallback. Do not assume every LibreTranslate
installation has models for every Indian language; check its `/languages`
endpoint before relying on it. If no provider is configured, the UI reports a
clear configuration message rather than claiming translation succeeded.

---

## 7. News aggregation

Sources are declared in [`backend/news/feeds.py`](backend/news/feeds.py). Each
entry has a key, publisher name, RSS URL, category and an optional
`breaking_source` flag. The default Google News edition is India (`hl=en-IN`,
`gl=IN`, `ceid=IN:en`). The collection includes The Hindu, NDTV, Hindustan Times,
The Indian Express, India Today, Mint, Business Standard and Economic Times,
plus site-restricted Google News searches for Times of India, WION, News18,
Deccan Herald, Firstpost, Scroll.in and The Print, alongside BBC, The Guardian,
Al Jazeera, DW and specialist publishers. The normal refresh
fetches 31 balanced feeds; `ingest_news --all` fetches all 47 configured feeds.

Publisher feeds and reuse terms vary. The Times of India's published RSS terms
restrict aggregation/redistribution without permission, so NewsHub uses a
site-restricted Google News search for TOI rather than directly ingesting its
RSS feed. Before any public or commercial deployment, review each publisher's
syndication terms, attribution rules and rate limits, and obtain permission
where required. A configured feed can fail or return no new content at any time.

Pipeline:

1. **Fetch** — RSS/Atom feeds and Google News topic/search feeds are fetched in
   parallel with per-request timeouts and a NewsHub user agent.
2. **Normalize** — HTML is stripped, publisher suffixes are removed *only when
   they match the known source*, relative/invalid URLs are discarded.
3. **Deduplicate** — tracking parameters are removed for comparison; a SHA-256
   key is built from the canonical URL. Near-identical headlines are suppressed
   only within the same publisher. Similar reports from different publishers are
   preserved so readers and NewsLens can compare independent coverage. For Google
   News wrapper URLs, publisher metadata is used to distinguish the source.
4. **Classify** — provider sections are preserved; every item also receives an
   ML prediction with a confidence score. Search results have no provider
   section, so the ML/rules result becomes the display category.
5. **Annotate** — sentiment is computed and stored; timestamp anomalies
   (future-dated feed items) are clamped.
6. **Store** — `update_or_create`-style upsert preserves editor overrides,
   view counts and publication status; articles are never duplicated.

Only headline, short description, image URL and a link back to the publisher
are stored for aggregated items. Full article text is stored only when the
provider shares it or an editor adds it with rights. Breaking labels are used
only from the provider's top-stories feed, within a 3-hour window; when nothing
qualifies, the UI says so and shows “latest headlines” instead.

---

## 8. Machine learning

### 8.1 Automatic categorization

- Corpus: `backend/news/ml/data/training_data.csv` — 324 hand-curated
  headline/description pairs covering nine sections, written for this project.
  “World News” rows are excluded from model training because that section is
  assigned from provider metadata; the model predicts the eight editorial
  categories from the brief.
- Features: TF-IDF word n-grams (1–2) unioned with character n-grams (3–5).
- Model: logistic regression (`C=1.0`, balanced class weights).
- Split: 75/25 stratified hold-out, `random_state=42`.

Actual output of `python manage.py train_classifier` in this workspace:

```
rows           : 289
train / test   : 216 / 73
accuracy       : 0.7808
macro F1       : 0.7791
weighted F1    : 0.7780
```

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| business | 0.86 | 0.67 | 0.75 | 9 |
| education | 0.88 | 0.78 | 0.82 | 9 |
| entertainment | 0.78 | 0.78 | 0.78 | 9 |
| health | 1.00 | 0.67 | 0.80 | 9 |
| politics | 0.75 | 1.00 | 0.86 | 9 |
| science | 0.69 | 1.00 | 0.82 | 9 |
| sports | 0.70 | 0.70 | 0.70 | 10 |
| technology | 0.75 | 0.67 | 0.71 | 9 |

**Caveat, stated plainly:** these numbers come from a small curated seed
corpus, not a public benchmark. They show the pipeline trains and evaluates
correctly but are optimistic for arbitrary real-world headlines. The complete
metrics, including the confusion matrix, are written to
`backend/news/ml/artifacts/metrics.json` by the training command and exposed at
`GET /api/ml/metrics/`.

The model is loaded lazily and retrained automatically if the artifact is
missing. After retraining, refresh stored predictions:

```bash
python manage.py reclassify_articles
```

Editors can accept or override predictions in **Admin → ML review**, or in the
Django admin at `/admin/`.

### 8.2 Recommendations

`news/ml/recommend.py` builds TF-IDF vectors over title (weighted twice),
description, available content and category; cosine similarity scores candidate
articles. Final ranking blends 78% similarity, 16% recency (7-day half-life)
and a preference boost (+0.30 for explicit interests, +0.08 for reading
history). The current article is always excluded and scores are returned in the
API (`match_score`, `match_similarity`) for evaluation.

For anonymous users, ranking falls back to recency plus stored engagement
(saves and views). For signed-in users with personalization enabled, the
profile is built from interests (weighted heavily), saved articles and recent
views. One saved sports story cannot override explicit technology interests.

### 8.3 Sentiment

The pretrained VADER lexicon scores the tone of the text. Labels are
**positive / negative / neutral** with a compound score. The UI and API repeat
that tone is not accuracy. If VADER is unavailable, a small built-in lexicon is
used and the response reports the fallback method.

---

## 9. Summaries

`POST /api/ai/summarize/` accepts an `article_id` (preferred) or raw
`title`/`text`, plus `length` = `short` or `detailed`.

- **No LLM configured:** extractive summarization. Sentences are ranked with
  TF-IDF and a title-overlap/position bonus, then emitted in reading order.
- **LLM configured:** a strict prompt tells the model to use only the supplied
  text, add no facts, and return a fixed number of sentences. Provider or
  network failures fall back to the extractive result with a visible warning.
- The response states `based_on` (`content`, `description`, `title`),
  `limited_content`, word count, method and a disclaimer. When only a
  headline/description exists, the UI explicitly says the summary covers
  limited information.

Summaries are cached for six hours per article, length and update timestamp.

---

## 10. Fact-check methodology (honest limits)

`POST /api/fact-check/` accepts any combination of claim, headline, article URL
and paragraph. URL metadata is fetched server-side to recover the headline and
description.

1. **Extract the claim** — first two sentences, capped at 500 characters.
2. **Retrieve evidence** — exact-phrase, keyword and fact-check-focused
   searches against India-edition Google News RSS and any configured JSON
   providers, run in parallel. Up to 30 results are requested per query;
   duplicate URLs are removed. Recent locally stored coverage is also examined.
3. **Score each item** — keyword coverage of the claim's *content* terms
   (reporting verbs such as “confirmed” are ignored when measuring coverage),
   plus weighted supporting/contradicting language cues. Supporting requires
   explicit confirming language **or** near-complete coverage (75% and at least
   four content terms) for direct factual reporting; contradicting always
   requires explicit correcting language plus 50% coverage and two matched
   terms. This is what prevents “NASA confirms an unrelated mission” from
   counting as support for a claim about NASA.
4. **Apply conservative thresholds** — two or more consistent items are needed
   for “supported” or “contradicted”; both sides produce “mixed”; anything less
   returns “insufficient evidence”. Absence of contradiction is never treated
   as proof.
5. **Gate verdicts on source establishment** — every evidence item records the
   publisher. Trusted status requires both a publisher-name allowlist match and
   a matching publisher domain (or a Google News wrapper carrying a known
   publisher label). This reduces false trust from arbitrary sites that merely
   claim to be Reuters, BBC or another outlet. This is a corroboration heuristic,
   not a truth oracle.
6. **Explain** — a templated explanation is generated from the counts. If an
   LLM is configured, it rewrites the explanation using only the collected
   evidence; it cannot change the verdict.
7. **Persist** — every submitted check stores its claim, verdict, confidence,
   evidence URLs, related stored articles and analysis notes.

Verdict labels:

- Supported by available evidence
- Contradicted by available evidence
- Mixed evidence
- Insufficient evidence

The allowlist lives in `backend/news/services/factcheck.py`
(`ESTABLISHED_SOURCES`). Evidence from other sites is still displayed with its
stance but cannot on its own produce a supported/contradicted verdict. The
allowlist can exclude valid local reporting, so verdicts remain conservative.

**Limits:** this is not a trained truth classifier, not a fake-news detector,
and not professional fact-checking. Keyword and cue scoring can misread
negation, sarcasm and context; search results depend on provider availability;
coverage is not independent verification. Every result carries a disclaimer and
links to the evidence used.

---

## 11. API reference

Base URL: `http://127.0.0.1:8000/api`. Authenticated requests use
`Authorization: Token <token>`.

### Auth and user

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register/` | username, email, password, password_confirm → token |
| POST | `/auth/login/` | `identifier` (username or email), `password` |
| POST | `/auth/logout/` | deletes the token (auth required) |
| GET/PATCH | `/auth/profile/` | profile details |
| GET/PUT | `/user/preferences/` | categories + personalization flag |
| GET | `/user/saved-news/` | saved articles (auth) |
| GET | `/users/<username>/` | public display name only |

### News

| Method | Path | Notes |
|---|---|---|
| GET | `/news/` | filters: `q`, `category`, `source`, `date=today\|week\|month`, `sort=latest\|oldest\|relevance`, `page`, `page_size` |
| GET | `/news/latest/` | newest first |
| GET | `/news/breaking/` | provider-flagged, 24h; honest fallback flag |
| GET | `/news/trending/` | topics with real counts + engaged stories |
| GET | `/news/search/?q=` | live provider search, dedupe, stored-match count |
| GET | `/news/category/<slug>/` | category feed |
| GET | `/news/<id>/` | detail + recommendations + view tracking |
| GET | `/news/<id>/recommendations/` | scored related articles |
| GET | `/news/recommended/` | personalized or popularity fallback |
| POST/DELETE | `/news/<id>/save/` | save / unsave (auth) |
| GET | `/categories/` | categories with published counts |
| GET | `/news/sources/` | configured feeds, stored publishers, API provider status |
| GET | `/health/` | liveness + stored article count |

### AI / ML

| Method | Path | Notes |
|---|---|---|
| POST | `/ai/summarize/` | `article_id` or `title`/`text`, `length` |
| POST | `/ai/sentiment/` | `article_id` or `text` |
| POST | `/ml/categorize/` | `title`, `description`, `content` |
| GET | `/ml/metrics/` | real evaluation metrics + model status |
| POST | `/fact-check/` | claim/headline/URL/content |
| GET | `/fact-check/<uuid>/` | stored result (owner or staff if owned) |
| GET | `/fact-check/history/` | signed-in user's recent checks |

### Admin (staff only, `/api/admin/…`)

`GET/POST news/`, `GET/PATCH/PUT/DELETE news/<id>/`,
`POST news/<id>/category/` (accept ML or override), `GET review-queue/`,
`GET/POST categories/`, `PATCH/DELETE categories/<id>/`, `GET users/`,
`GET fact-checks/`, `GET dashboard/`, `POST ingest/`.

Errors use JSON `{ "detail": "...", "code": "..." }` with appropriate status
codes; stack traces and secrets are never returned.

---

## 12. Testing

```bash
cd backend
source .venv/bin/activate
python manage.py test
```

74 tests cover:

- URL normalization, publisher suffix handling, dedupe key stability, near-duplicate detection
- aggregation with mocked providers (create/update/dedupe/editor override/invalid URLs)
- auth: register, duplicate username/email, weak passwords, login by email, logout invalidation, permissions
- preferences round-trip and validation
- save/unsave, saved list, auth requirement
- feed filtering, date filters, oldest sort, breaking fallback honesty, trending counts
- search empty state, invalid query, provider outage 503
- recommendations exclude the current article and expose scores
- classifier labels/metrics, sentiment labels, extractive summary and limited-content warning
- fact-check contradicted/supported/insufficient outcomes, unknown-source rejection, direct high-coverage reporting, owner-only detail access, related stored articles
- admin permission denial, article CRUD, duplicate URL rejection, dashboard shape, ML review actions, category deletion guard

Network calls are mocked in tests; the suite does not depend on provider uptime.
Frontend verification is a production build (`npm run build`) plus the running
dev server and API proxy; interactive browser and mobile checks are left to the
reviewer.

---

## 13. Production checklist

1. Set `DJANGO_DEBUG=false`, a strong `DJANGO_SECRET_KEY`, and explicit
   `DJANGO_ALLOWED_HOSTS` / `DJANGO_CORS_ALLOWED_ORIGINS`.
2. Switch `DATABASES` to PostgreSQL (the ORM layer is already portable) and run
   `migrate`.
3. Serve Django behind HTTPS (Gunicorn/uWSGI + Nginx) and the React build from
   a static host or CDN. Configure `/api` proxying to Django.
4. Keep all provider and LLM keys in environment variables only.
5. Run `ingest_news --all` on a scheduler and monitor failures; respect each
   provider's terms and rate limits. Cache TTLs and timeouts are configurable.
6. Consider Redis for the Django cache if running multiple processes
   (`LocMemCache` is per-process).
7. Review throttle rates (`fact_check`, `ai`, `auth`) for your traffic.
8. Retrain the classifier after meaningful dataset changes and run
   `reclassify_articles`.
9. Do not publish automated labels as verified truth; keep the disclaimers.

---

## 14. Known limitations and roadmap

- Classifier trained on a 324-row curated seed corpus; accuracy is not a
  real-world benchmark. A larger labelled dataset is the biggest quality win.
- Recommendations are content-based only. Collaborative filtering needs
  interaction volume this project does not yet have.
- Article text is limited to what a publisher supplies inline in its RSS/Atom feed or what an editor enters. NewsHub does not scrape publisher webpages or bypass paywalls; some article pages therefore show a publisher summary and link to the original report.
- Fact-checking depends on provider search quality and lexical stance cues.
  Domain checks, Indian fact-check publishers and broader search variants reduce
  some failure modes, but claim decomposition, a calibrated NLI model and
  official fact-check APIs would be the next step.
- No free-form article Q&A. The optional LLM is used for summaries, fact-check explanations and generated briefings. Translation uses Sarvam Translate, LibreTranslate or the LLM fallback; external provider credentials are required.
- No email verification or password reset flow (Django's built-ins can be
  wired in).
- The React app has component-level structure but no dedicated component test
  suite yet; API behaviour is covered by the Django regression tests.

---

## 15. Attribution and responsible use

NewsHub stores and displays headlines, descriptions, image URLs and source
links provided by publishers' public feeds. When a feed explicitly supplies
inline article text, NewsHub may display that publisher-provided text; editors
may also enter content. NewsHub does not scrape publisher webpages or bypass
paywalls. Copyright remains with the relevant publisher, attribution is shown,
and every article links to its original source. Aggregation must respect each
provider's terms and applicable law.

Automated classification, sentiment, summaries and fact-check assessments are
informational signals, not verdicts. Always read the cited reporting and consult
professional fact-checkers for consequential decisions.

---

## 16. Reader and intelligence features added in this revision

| Feature | Implementation | Requirements / limits |
|---|---|---|
| Multilingual news | Article-page translation control for English, Malayalam, Hindi, Tamil, Telugu and Kannada. | Configure `SARVAM_API_KEY` (recommended), a LibreTranslate endpoint, or `LLM_API_KEY`. Translates only text stored in NewsHub; without a provider key it reports a setup error instead of fabricated output. |
| AI daily briefing | `/briefing` page and `/api/ai/daily-briefing/` endpoint. Uses recent articles and selected interests for signed-in users. | Uses the configured LLM for generated prose; otherwise returns an explicit deterministic briefing from the stored articles. |
| Advanced search | Exact phrase, excluded words, author, date range, image availability, category, publisher, date and relevance filters. | Operates on the indexed NewsHub article corpus; topic search can first fetch fresh provider results. |
| Reading analytics | `/analytics` page and private account analytics API. Counts views, saved items and time spent on article pages. | Requires login. Reading time is recorded in 30-second intervals and is an estimate, not a measure of attention. |
| NewsLens | Article-level cross-publisher story matching using lexical TF-IDF cosine similarity, title/content overlap, entity-like phrase overlap, category and publication-time signals. | Scores are relevance estimates, not transformer-based semantic understanding or proof of the same event or publisher bias. Match explanations are surfaced to the reader. |
| TruthTrace | Signed-in users can track a headline/claim and revisit a chronological collection of related reports. | New related reports are attached when the tracked claim is opened again. Related reports are labelled as context, not automatically as evidence for or against the claim. |

### Article content and publisher rights

The ingestion pipeline now extracts article text when an RSS/Atom provider supplies it inline (for example, a full-text `content:encoded` field). The article page displays that available text, including paragraph breaks. It does **not** crawl paywalls or scrape complete publisher webpages. Many feeds supply only a headline and short description; for those items NewsHub shows the available summary and a direct link to the publisher's original article. An editor can also add licensed or authored article text in the admin interface.

### New API routes

- `POST /api/ai/translate/` — translate an article's stored text; body: `article_id`, `target_language`.
- `GET /api/ai/daily-briefing/` — recent story briefing, optionally personalized for signed-in users.
- `GET /api/news/{id}/newslens/` — similar coverage and phrase-level comparison.
- `POST /api/analytics/reading-event/` — authenticated reading-time event; body: `article_id`, `duration_seconds`.
- `GET /api/analytics/reading/` — authenticated 30-day reading analytics.
- `GET /api/truth-trace/` — list the signed-in user's tracked claims.
- `POST /api/truth-trace/` — create a tracked claim; body: `article_id` and/or `claim`.
- `GET /api/truth-trace/{id}/` — refresh and retrieve its related-report timeline.
- `DELETE /api/truth-trace/{id}/` — delete a tracked claim.

### Optional AI configuration

Copy `backend/.env.example` to `backend/.env`. Set `SARVAM_API_KEY` to enable Indian-language translations (recommended), or configure a LibreTranslate endpoint / `LLM_API_KEY` fallback. `LLM_API_KEY` also enables abstractive summaries and generated daily-briefing prose. Keep all provider keys on the backend. Without a translation provider, the API returns an explicit configuration error rather than fabricated translations.

---

## 17. Production deployment with Docker Compose

The repository includes a production-oriented Docker setup: Django/Gunicorn, PostgreSQL, WhiteNoise static assets, and Nginx serving the React build and reverse-proxying API/admin requests.

1. Install Docker Engine and the Docker Compose plugin.
2. Copy `.env.docker.example` to `.env` in the repository root.
3. Replace `DJANGO_SECRET_KEY` and `DB_PASSWORD` with unique, long random values. Set `DJANGO_ALLOWED_HOSTS` to the deployment hostnames.
4. For a public HTTPS deployment behind a TLS-terminating proxy, set `DJANGO_CSRF_TRUSTED_ORIGINS` to the exact `https://` origins, set `DJANGO_SECURE_SSL_REDIRECT=true`, and set `DJANGO_SECURE_COOKIES=true`. Ensure the proxy forwards the original HTTPS scheme. Do not enable HSTS until HTTPS is working correctly. The example Compose environment keeps secure cookies off for local HTTP testing; turn them on for a public HTTPS deployment.
5. Start the stack:

```bash
docker compose up --build -d
```

The backend container runs migrations, seeds categories, trains the local classifier (with a non-fatal fallback if training cannot run), collects static files and starts Gunicorn. The frontend is served through Nginx on `APP_PORT` (80 by default). PostgreSQL data persists in the `postgres_data` volume.

Create the first admin user:

```bash
docker compose exec backend python manage.py createsuperuser
```

Refresh news feeds:

```bash
docker compose exec backend python manage.py ingest_news --all
```

Check the deployment at `/api/health/` and the admin interface at `/admin/` on the same host. Configure external DNS/TLS and a scheduled ingestion task on the host/platform for ongoing updates; this repository does not provision a domain name, TLS certificate, LLM key, NewsAPI key or GNews key.

### Local development remains supported

The original SQLite + Vite development setup is unchanged. Use the local instructions in section 5. For deployment without Docker, set `DB_ENGINE=postgresql` and the `DB_*` values in `backend/.env` if you prefer PostgreSQL. With `DJANGO_DEBUG=false`, provide a real `DJANGO_SECRET_KEY`; the application now refuses to start with the development fallback secret.

---

## 18. Verification notes

The project source has been syntax-checked with Python's bytecode compiler. Full Django tests and the Vite production build could not be executed in the packaging environment because Django and the frontend npm packages were not installed and outbound package-index access was unavailable. Run the commands below in an environment with network/package access before public deployment:

```bash
# Backend
cd backend
python -m pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test

# Frontend (from the repository root in another terminal)
cd frontend
npm ci
npm run build
```

Do not treat a successful archive creation as a substitute for staging tests with real news-provider connectivity and configured production secrets.
