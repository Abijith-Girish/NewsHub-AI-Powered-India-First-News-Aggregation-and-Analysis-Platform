# NewsHub India-first refresh

## Changes in this revision

- Switched Google News topic and search feeds to the India edition (`en-IN`, `IN`, `IN:en`).
- Expanded the curated feed configuration to 47 feeds, including The Hindu, NDTV, Hindustan Times, The Indian Express, India Today, Mint, Business Standard and Economic Times RSS feeds, plus Google News site-restricted searches for Times of India, WION, News18, Deccan Herald, Firstpost, Scroll.in and The Print.
- Expanded the normal refresh to 31 balanced India and international feeds and the full refresh to all 47 feeds.
- Raised the homepage first-page request from 9 to 18 articles and category-page requests from 12 to 18.
- Changed near-duplicate handling to suppress repeats within the same publisher while preserving comparable reports from other publishers. Google News publisher metadata is used when article links are Google News wrappers.
- Improved NewsLens matching with headline-token overlap, TF-IDF text similarity, named-entity-like phrase overlap, article-content overlap, category and publication-time signals. The returned score is a retrieval estimate, not proof of same-event identity or bias.
- Improved TruthTrace claim retrieval using TF-IDF, claim-term coverage and entity-like phrase overlap. Reports remain context unless optional LLM classification can cautiously classify explicit support or contradiction.
- Improved FactCheck query variants, stored-article retrieval, India-focused publisher allowlisting and sentence-scoped support/contradiction cues. The system remains a cautious automated assessment, not a definitive fact-checker.
- Added Sarvam Translate support for Hindi, Malayalam, Tamil, Telugu and Kannada, with LibreTranslate and OpenAI-compatible LLM fallbacks. A provider API key or endpoint is required for non-English translation.
- Kept a local extractive summarization fallback and optional chunked LLM summarization. The response warns when the stored publisher text is only a headline/description or other limited content.
- Applied `en-IN` / `Asia/Kolkata` date formatting to briefings and related feature timestamps.
- Enforced India-local date validation in advanced search in both the frontend and API: invalid, future and reversed ranges are rejected.

## Verification performed in the build environment

- Python source compilation: passed.
- Frontend JavaScript/JSX syntax transpilation: passed for 44 files.
- Docker Compose YAML parsing: passed.
- ZIP integrity: checked after packaging.

## Checks not performed

- Django unit tests and migrations were not executed because Django and Django REST Framework are not installed in the build environment.
- The frontend production build was not executed because npm dependencies are not present and the package registry could not be reached in offline mode.
- Docker image builds and live publisher-feed tests were not executed because Docker is not installed in the build environment.

## External-service and content limitations

- Set `SARVAM_API_KEY` (recommended) or configure LibreTranslate / `LLM_API_KEY` to enable translation. No API credential is bundled.
- An OpenAI-compatible `LLM_API_KEY` enables abstractive summaries and generated briefing prose; without it, summaries use the local extractive method and briefings use the deterministic stored-article fallback.
- Full article text is displayed only when supplied in publisher feed content or entered by an editor. NewsHub does not bypass paywalls or scrape protected article pages.
- Some publisher feeds can block, throttle, move or return no articles. Check ingestion logs and publisher terms before public deployment. Times of India uses a site-restricted Google News feed rather than direct RSS ingestion due to publisher syndication restrictions.
- FactCheck, NewsLens and TruthTrace are automated information aids. Their scores and labels must not be presented as guaranteed truth, independent confirmation, political-bias detection or legal findings.


## Publisher article extraction update

- Added a bounded, on-demand publisher-page extraction service using Trafilatura and BeautifulSoup/JSON-LD fallback parsing.
- Added redirect and public-address checks, robots.txt handling, response-size limits, timeouts, and explicit handling for access restrictions.
- Added a throttled article-content endpoint and a reader action to load accessible publisher text.
- Summary and translation requests now share the cached extraction result and report `full`, `partial`, or `headline_only` source coverage.
- Extracted page text is temporary cache content and is not persisted in the Article database.
- Added regression tests for extraction cleanup, JSON-LD extraction, URL safety, and robots-denied fallback.
