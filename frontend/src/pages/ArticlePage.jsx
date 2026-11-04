import {
  AlertTriangle,
  ArrowUpRight,
  CalendarDays,
  ChevronRight,
  Clock,
  Gauge,
  ScanSearch,
  Sparkles,
  UserRound,
  Wand2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import ArticleCard from '../components/ArticleCard';
import ArticleImage from '../components/ArticleImage';
import SaveButton from '../components/SaveButton';
import SentimentBadge from '../components/SentimentBadge';
import { SkeletonLines } from '../components/Skeletons';
import { ErrorState, NoteBanner } from '../components/States';
import SummaryPanel from '../components/SummaryPanel';
import { useAuth } from '../context/AuthContext';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { aiApi, apiErrorMessage, newsApi } from '../lib/api';
import { NewsLensPanel, TruthTracePanel } from '../components/ArticleInsights';
import { cx, formatDateTime, percent, timeAgo } from '../lib/format';

const CATEGORY_SOURCE_LABELS = {
  feed: 'Publisher section',
  ml: 'ML classifier',
  rule: 'Keyword rules',
  manual: 'Editor override',
};

function ArticleSkeleton() {
  return (
    <div className="container-page py-8">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="skeleton h-3 w-28" />
        <div className="skeleton h-10 w-full" />
        <div className="skeleton h-10 w-4/5" />
        <div className="skeleton h-4 w-2/3" />
        <div className="skeleton mt-6 aspect-[16/9] w-full" />
        <SkeletonLines count={8} />
      </div>
    </div>
  );
}

export default function ArticlePage() {
  const { id } = useParams();
  const { isAuthenticated } = useAuth();
  const { data, loading, error, reload } = useFetch(
    () => newsApi.article(id).then((res) => res.data),
    [id]
  );

  const [showSummary, setShowSummary] = useState(false);
  const [sentiment, setSentiment] = useState(null);
  const [sentimentBusy, setSentimentBusy] = useState(false);
  const [sentimentError, setSentimentError] = useState('');
  const [targetLanguage, setTargetLanguage] = useState('ml');
  const [translation, setTranslation] = useState(null);
  const [translationBusy, setTranslationBusy] = useState(false);
  const [translationError, setTranslationError] = useState('');
  const [publisherContent, setPublisherContent] = useState(null);
  const [publisherContentBusy, setPublisherContentBusy] = useState(false);
  const [publisherContentError, setPublisherContentError] = useState('');

  const article = data?.article;
  const recommendations = data?.recommendations || [];

  useDocumentTitle(article?.title);

  useEffect(() => {
    if (!article?.id || !isAuthenticated) return undefined;
    let segmentStarted = document.visibilityState === 'visible' ? Date.now() : null;

    const flushVisibleTime = () => {
      if (segmentStarted === null) return;
      const seconds = Math.floor((Date.now() - segmentStarted) / 1000);
      segmentStarted = null;
      if (seconds >= 5) {
        newsApi.recordReading({
          article_id: article.id,
          duration_seconds: Math.min(seconds, 1800),
        }).catch(() => {});
      }
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        flushVisibleTime();
      } else if (segmentStarted === null) {
        segmentStarted = Date.now();
      }
    };

    const interval = window.setInterval(() => {
      if (segmentStarted !== null && Date.now() - segmentStarted >= 30000) {
        flushVisibleTime();
        if (document.visibilityState === 'visible') segmentStarted = Date.now();
      }
    }, 5000);
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      flushVisibleTime();
    };
  }, [article?.id, isAuthenticated]);

  useEffect(() => {
    setSentiment(null);
    setSentimentError('');
    setShowSummary(false);
    setTranslation(null);
    setTranslationError('');
    setPublisherContent(null);
    setPublisherContentError('');
  }, [id]);

  useEffect(() => {
    if (article?.sentiment) setSentiment(article.sentiment);
  }, [article]);

  if (loading) return <ArticleSkeleton />;

  if (error || !article) {
    return (
      <div className="container-page py-16">
        <ErrorState
          message={error || 'This article could not be found. It may have been removed by its publisher.'}
          onRetry={reload}
        />
        <div className="mt-6 text-center">
          <Link to="/" className="btn-secondary">Back to latest news</Link>
        </div>
      </div>
    );
  }

  async function analyzeSentiment() {
    setSentimentBusy(true);
    setSentimentError('');
    try {
      const { data: payload } = await aiApi.sentiment({ article_id: article.id });
      setSentiment(payload);
    } catch (err) {
      setSentimentError(apiErrorMessage(err));
    } finally {
      setSentimentBusy(false);
    }
  }

  async function translateArticle() {
    setTranslationBusy(true);
    setTranslationError('');
    try {
      const { data: payload } = await aiApi.translate({ article_id: article.id, target_language: targetLanguage });
      setTranslation(payload);
    } catch (err) {
      setTranslationError(apiErrorMessage(err));
    } finally {
      setTranslationBusy(false);
    }
  }

  async function loadPublisherContent() {
    setPublisherContentBusy(true);
    setPublisherContentError('');
    try {
      const { data: payload } = await newsApi.articleContent(article.id);
      setPublisherContent(payload);
    } catch (err) {
      setPublisherContentError(apiErrorMessage(err));
    } finally {
      setPublisherContentBusy(false);
    }
  }

  const availableArticleText = publisherContent?.content || article.content || '';
  const availableWordCount = availableArticleText.trim() ? availableArticleText.trim().split(/\s+/).length : 0;
  const contentStatus = publisherContent?.content_status || (availableWordCount >= 120 ? 'full' : availableWordCount >= 45 ? 'partial' : 'headline_only');
  const paragraphs = availableArticleText
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);

  return (
    <div className="container-page py-8">
      <nav className="flex flex-wrap items-center gap-1.5 text-xs text-ink-500" aria-label="Breadcrumb">
        <Link to="/" className="hover:text-ink-900 dark:hover:text-white">Home</Link>
        <ChevronRight className="h-3 w-3" aria-hidden />
        {article.category ? (
          <Link to={`/category/${article.category.slug}`} className="hover:text-ink-900 dark:hover:text-white">
            {article.category.name}
          </Link>
        ) : (
          <span>News</span>
        )}
        <ChevronRight className="h-3 w-3" aria-hidden />
        <span className="max-w-[24rem] truncate text-ink-700 dark:text-ink-300">{article.title}</span>
      </nav>

      <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <article>
          <div className="flex flex-wrap items-center gap-2">
            {article.is_breaking && (
              <span className="rounded-sm bg-accent-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Breaking
              </span>
            )}
            {article.category && (
              <Link to={`/category/${article.category.slug}`} className="eyebrow">
                {article.category.name}
              </Link>
            )}
          </div>

          <h1 className="mt-3 text-balance font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl lg:text-[2.75rem]">
            {article.title}
          </h1>

          {article.description && (
            <p className="mt-3 max-w-3xl font-display text-lg leading-7 text-ink-600 dark:text-ink-300">
              {article.description}
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 border-y border-ink-200 py-3 text-xs text-ink-500 dark:border-ink-800 dark:text-ink-400">
            <span className="font-semibold uppercase tracking-wide text-ink-800 dark:text-ink-200">
              {article.source}
            </span>
            {article.author && (
              <span className="inline-flex items-center gap-1">
                <UserRound className="h-3.5 w-3.5" aria-hidden /> {article.author}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="h-3.5 w-3.5" aria-hidden />
              <time dateTime={article.published_at}>{formatDateTime(article.published_at)}</time>
            </span>
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" aria-hidden /> {timeAgo(article.published_at)}
            </span>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <SaveButton article={article} label />
            <button type="button" className="btn-secondary" onClick={() => setShowSummary((open) => !open)}>
              <Sparkles className="h-4 w-4" /> Summarize article
            </button>
            <a href={article.source_url} target="_blank" rel="noopener noreferrer" className="btn-primary">
              Read at {article.source || 'publisher'} <ArrowUpRight className="h-4 w-4" />
            </a>
          </div>

          {article.image_url && (
            <figure className="mt-6 overflow-hidden rounded-2xl border border-ink-200 dark:border-ink-800">
              <div className="aspect-[16/9] max-h-[460px] w-full">
                <ArticleImage
                  src={article.image_url}
                  alt={article.title}
                  category={article.category?.slug}
                  priority
                />
              </div>
              <figcaption className="bg-white px-4 py-2 text-[11px] text-ink-400 dark:bg-ink-900 dark:text-ink-500">
                Image supplied by {article.source || 'the publisher'} in its feed. Rights remain with the publisher.
              </figcaption>
            </figure>
          )}

          {showSummary && (
            <div className="mt-6">
              <SummaryPanel articleId={article.id} onClose={() => setShowSummary(false)} />
            </div>
          )}

          <section className="mt-5 rounded-xl border border-ink-200 bg-white p-4 dark:border-ink-800 dark:bg-ink-900">
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="article-language" className="text-xs font-semibold text-ink-600 dark:text-ink-300">Translate available article text</label>
              <select id="article-language" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)} className="select w-auto min-w-32">
                <option value="ml">Malayalam</option><option value="hi">Hindi</option><option value="ta">Tamil</option><option value="te">Telugu</option><option value="kn">Kannada</option><option value="en">English</option>
              </select>
              <button type="button" onClick={translateArticle} disabled={translationBusy} className="btn-secondary btn-sm">{translationBusy ? 'Translating…' : 'Translate'}</button>
            </div>
            {translationError && <p className="mt-2 text-xs text-rose-600">{translationError}</p>}
            {translation && <div className="mt-4 border-t border-ink-100 pt-4 dark:border-ink-800"><p className="text-xs font-bold uppercase tracking-wider text-ink-500">{translation.target_language_name} translation</p><div className="prose-news mt-3 whitespace-pre-line">{translation.translated_text}</div><p className="mt-3 text-xs text-ink-400">{translation.note}</p></div>}
          </section>

          <div className="prose-news mt-6">
            {paragraphs.length ? (
              <>
                <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                  {publisherContent?.content_source === 'publisher_page'
                    ? 'Accessible article text extracted from publisher page'
                    : article.content
                      ? 'Article text supplied by publisher feed or editor'
                      : 'Available publisher text'}
                </p>
                {paragraphs.map((paragraph, index) => (
                  <p key={index} className="mb-4">{paragraph}</p>
                ))}
                {publisherContent?.note && (
                  <NoteBanner>{publisherContent.note}</NoteBanner>
                )}
              </>
            ) : (
              <div className="space-y-4">
                <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400">Publisher-provided summary</p>
                {article.description && <p>{article.description}</p>}
                <NoteBanner>
                  NewsHub has the headline and short description shared in the feed. It can
                  attempt to retrieve publicly accessible article text, but publisher
                  restrictions may prevent retrieval. The original publisher remains the
                  authoritative source: {' '}
                  <a href={article.source_url} target="_blank" rel="noopener noreferrer" className="font-semibold underline">
                    {article.source || 'read the original article'}
                  </a>.
                </NoteBanner>
              </div>
            )}
            {!publisherContent && (!availableArticleText || contentStatus !== 'full') && (
              <div className="mt-4 not-prose">
                <button type="button" className="btn-secondary btn-sm" onClick={loadPublisherContent} disabled={publisherContentBusy}>
                  {publisherContentBusy ? 'Checking publisher page…' : 'Load available article text'}
                </button>
              </div>
            )}
            {publisherContentError && (
              <p className="mt-2 text-xs text-rose-600">{publisherContentError}</p>
            )}
            {publisherContent && publisherContent.content_status !== 'full' && (
              <p className="mt-2 text-[11px] text-ink-500 dark:text-ink-400">
                {publisherContent.note || 'The publisher did not make the full article text available.'}
              </p>
            )}
          </div>

          <section className="mt-10 rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Check this story</h2>
                <p className="mt-1 max-w-xl text-sm leading-6 text-ink-500 dark:text-ink-400">
                  Run an evidence-based assessment of the headline, or find out how the
                  language is framed. Both are informational, not verdicts.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={analyzeSentiment}
                  disabled={sentimentBusy}
                >
                  <Gauge className="h-3.5 w-3.5" />
                  {sentimentBusy ? 'Analyzing tone…' : 'Analyze tone'}
                </button>
                <Link
                  to="/fact-check"
                  state={{ claim: article.title, article_title: article.title, source_url: article.source_url }}
                  className="btn-secondary btn-sm"
                >
                  <ScanSearch className="h-3.5 w-3.5" /> Fact check this
                </Link>
              </div>
            </div>

            {sentimentError && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-rose-600">
                <AlertTriangle className="h-3.5 w-3.5" /> {sentimentError}
              </p>
            )}

            {sentiment?.label && (
              <div className="mt-4 rounded-xl border border-ink-200 bg-ink-50 p-4 dark:border-ink-700 dark:bg-ink-800/40">
                <div className="flex flex-wrap items-center gap-2">
                  <SentimentBadge label={sentiment.label} score={sentiment.score} showScore />
                  <span className="text-[11px] text-ink-500">
                    {sentiment.method === 'vader_lexicon' ? 'Pretrained VADER lexicon' : 'Analyzer'} ·{' '}
                    score {Number(sentiment.score ?? 0).toFixed(3)}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-ink-600 dark:text-ink-400">
                  {sentiment.explanation ||
                    'Sentiment describes the tone of the wording. It does not tell you whether the article is accurate.'}
                </p>
              </div>
            )}
          </section>

          <section className="mt-10">
            <div className="mb-4 flex items-end justify-between">
              <div>
                <p className="eyebrow">Content-based recommendations</p>
                <h2 className="mt-1 text-2xl font-bold">Related reporting</h2>
              </div>
              <Link to="/explore" className="text-xs font-medium text-ink-500 hover:text-ink-900 dark:hover:text-white">
                More topics
              </Link>
            </div>
            {recommendations.length ? (
              <div className="grid gap-5 sm:grid-cols-2">
                {recommendations.slice(0, 4).map((item) => (
                  <ArticleCard key={item.id} article={item} />
                ))}
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-ink-300 p-5 text-sm text-ink-500 dark:border-ink-700">
                No similar stored articles yet. Recommendations appear as the corpus grows.
              </p>
            )}
      {recommendations.length > 0 && (
              <p className="mt-3 text-[11px] text-ink-400 dark:text-ink-500">
                Ranked with TF-IDF cosine similarity plus recency; scores are returned by the
                API for evaluation. Example: “{recommendations[0].title.slice(0, 64)}…” at{' '}
                {recommendations[0].match_score ?? '—'}.
              </p>
            )}
          </section>
        </article>

        <aside className="space-y-5">
          <section className="card p-5">
            <h2 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-ink-500">
              <Sparkles className="h-3.5 w-3.5 text-signal-500" aria-hidden /> AI classification
            </h2>
            <div className="mt-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-ink-600 dark:text-ink-400">Displayed section</span>
                <span className="text-sm font-semibold">{article.category?.name || 'Uncategorised'}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-ink-600 dark:text-ink-400">Assigned by</span>
                <span className="text-sm font-medium">
                  {CATEGORY_SOURCE_LABELS[article.category_source] || '—'}
                </span>
              </div>
              {article.ml_category && (
                <>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-ink-600 dark:text-ink-400">ML prediction</span>
                    <span className="text-sm font-medium">{article.ml_category.name}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-ink-600 dark:text-ink-400">Confidence</span>
                    <span className="text-sm font-medium">{percent(article.ml_confidence)}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-ink-200 dark:bg-ink-800">
                    <div
                      className="h-full rounded-full bg-signal-500"
                      style={{ width: `${Math.min(100, Math.round((article.ml_confidence || 0) * 100))}%` }}
                    />
                  </div>
                </>
              )}
            </div>
            <p className="mt-3 text-[11px] leading-5 text-ink-400 dark:text-ink-500">
              A statistical prediction from a locally trained TF-IDF + logistic regression
              model. It can be wrong; editors can override it.
            </p>
          </section>

          <section className="card p-5">
            <h2 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-ink-500">
              <Wand2 className="h-3.5 w-3.5" aria-hidden /> Source
            </h2>
            <p className="mt-3 font-display text-lg font-semibold">{article.source || 'Unknown publisher'}</p>
            {article.author && (
              <p className="mt-1 text-xs text-ink-500">By {article.author}</p>
            )}
            <a
              href={article.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary btn-sm mt-4 w-full"
            >
              Original article <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
            <p className="mt-3 break-all text-[11px] leading-4 text-ink-400">{article.publisher_domain}</p>
          </section>

          {!isAuthenticated && (
            <section className="rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
              <h2 className="text-sm font-bold">Save and personalize</h2>
              <p className="mt-1.5 text-xs leading-5 text-ink-500 dark:text-ink-400">
                Create an account to bookmark articles and rank your feed around the
                sections you follow.
              </p>
              <Link to="/register" className={cx('btn-primary btn-sm mt-3 w-full')}>
                Create a free account
              </Link>
            </section>
          )}
        </aside>
      </div>
      <div className="mt-8 grid gap-5 lg:grid-cols-2">
        <NewsLensPanel articleId={article.id} />
        <TruthTracePanel article={article} isAuthenticated={isAuthenticated} />
      </div>
    </div>
  );
}
