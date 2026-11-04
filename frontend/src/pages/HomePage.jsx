import { ArrowRight, Bookmark, Layers, ScanSearch, Sparkles, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import ArticleCard from '../components/ArticleCard';
import BreakingSection from '../components/BreakingSection';
import CategoryChips from '../components/CategoryChips';
import SectionHeader from '../components/SectionHeader';
import { SkeletonGrid, SkeletonLines } from '../components/Skeletons';
import { EmptyState, ErrorState, NoteBanner } from '../components/States';
import TrendingRail from '../components/TrendingRail';
import { useAuth } from '../context/AuthContext';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { newsApi } from '../lib/api';
import { cx } from '../lib/format';

const PAGE_SIZE = 18;

export default function HomePage() {
  useDocumentTitle(null);
  const { user } = useAuth();
  const [articles, setArticles] = useState([]);
  const [meta, setMeta] = useState(null);
  const [page, setPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [activeCategory, setActiveCategory] = useState('technology');

  const breaking = useFetch(() => newsApi.breaking().then((res) => res.data), []);
  const trending = useFetch(() => newsApi.trending().then((res) => res.data), []);
  const recommended = useFetch(
    () => newsApi.recommended({ limit: 4 }).then((res) => res.data),
    [user?.id]
  );
  const categories = useFetch(() => newsApi.categories().then((res) => res.data.results), []);
  const latest = useFetch(
    () => newsApi.list({ page: 1, page_size: PAGE_SIZE }).then((res) => res.data),
    []
  );
  const spotlight = useFetch(
    () => newsApi.list({ category: activeCategory, page_size: 6 }).then((res) => res.data),
    [activeCategory]
  );

  useEffect(() => {
    if (latest.data) {
      setArticles(latest.data.results || []);
      setMeta(latest.data);
      setPage(1);
    }
  }, [latest.data]);

  async function loadMore() {
    if (loadingMore || !meta) return;
    setLoadingMore(true);
    try {
      const { data } = await newsApi.list({ page: page + 1, page_size: PAGE_SIZE });
      setArticles((current) => [...current, ...(data.results || [])]);
      setMeta(data);
      setPage(data.page);
    } catch {
      // The existing list stays usable; the button can be retried.
    } finally {
      setLoadingMore(false);
    }
  }

  const categoryList = categories.data || [];
  const hasMore = meta && meta.page < meta.pages;

  return (
    <div className="container-page py-6 sm:py-8">
      <BreakingSection data={breaking.data} loading={breaking.loading} />
      {breaking.error && (
        <div className="mt-4">
          <NoteBanner tone="warning">{breaking.error}</NoteBanner>
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-y border-ink-200 py-3 dark:border-ink-800">
        <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-ink-500">
          <Layers className="h-3.5 w-3.5" aria-hidden /> Browse sections
        </div>
        <CategoryChips categories={categoryList} className="max-w-full" />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SectionHeader
            eyebrow="Across all publishers"
            title="Latest news"
            description="Fresh reporting from multiple sources, deduplicated and sorted by publication time."
            to="/explore"
            linkLabel="Explore all"
          />

          {latest.loading && !articles.length && <SkeletonGrid count={4} columns="sm:grid-cols-2" />}

          {latest.error && !articles.length && (
            <ErrorState message={latest.error} onRetry={latest.reload} />
          )}

          {!latest.loading && !latest.error && !articles.length && (
            <EmptyState
              title="No articles are stored yet"
              message="NewsHub could not retrieve any headlines from its configured providers. Check the provider status and try again."
              action={<Link to="/explore" className="btn-primary">Open search</Link>}
            />
          )}

          {articles.length > 0 && (
            <>
              <div className="grid gap-5 sm:grid-cols-2">
                {articles.map((article, index) => (
                  <ArticleCard key={article.id} article={article} priority={index < 2} />
                ))}
              </div>
              <div className="mt-6 flex flex-col items-center gap-2">
                {hasMore ? (
                  <button
                    type="button"
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="btn-secondary min-w-40"
                  >
                    {loadingMore ? 'Loading…' : 'Load more stories'}
                  </button>
                ) : (
                  <p className="text-xs text-ink-400">You have reached the end of the stored feed.</p>
                )}
                {meta && (
                  <p className="text-[11px] text-ink-400">
                    Showing {articles.length} of {meta.count} stored articles
                  </p>
                )}
              </div>
            </>
          )}
        </div>

        <aside className="space-y-6">
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
              <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider">
                <Sparkles className="h-4 w-4 text-signal-500" aria-hidden />
                {recommended.data?.mode === 'personalized' ? 'For you' : 'Popular now'}
              </h2>
              {recommended.data?.mode === 'personalized' && (
                <Link to="/profile" className="text-xs text-ink-500 hover:text-ink-900 dark:hover:text-white">
                  Tune
                </Link>
              )}
            </div>
            <div className="px-5 py-2">
              {recommended.loading && <SkeletonLines count={6} />}
              {recommended.error && <p className="py-3 text-xs text-rose-600">{recommended.error}</p>}
              {recommended.data?.results?.length ? (
                <div className="divide-y divide-ink-100 dark:divide-ink-800">
                  {recommended.data.results.map((article) => (
                    <ArticleCard key={article.id} article={article} variant="compact" />
                  ))}
                </div>
              ) : (
                !recommended.loading &&
                !recommended.error && (
                  <p className="py-4 text-sm text-ink-500">Recommendations appear after the first refresh.</p>
                )
              )}
            </div>
            <p className="border-t border-ink-100 px-5 py-3 text-[11px] leading-4 text-ink-400 dark:border-ink-800 dark:text-ink-500">
              {recommended.data?.note ||
                'Personalized picks use your chosen interests, saved articles and reading history.'}
            </p>
          </section>

          <TrendingRail data={trending.data} loading={trending.loading} />

          <section className="rounded-2xl border border-ink-200 bg-ink-900 p-5 text-white dark:border-ink-700">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-white/50">
              News literacy
            </p>
            <h2 className="mt-1.5 font-display text-xl font-bold">Check before you share</h2>
            <p className="mt-2 text-sm leading-6 text-white/70">
              Paste a claim and NewsHub retrieves related reporting, labels supporting and
              contradicting evidence, and shows every source it used.
            </p>
            <Link to="/fact-check" className="btn mt-4 bg-white py-2 text-xs text-ink-900 hover:bg-ink-100">
              Open fact check <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </section>
        </aside>
      </div>

      <section className="mt-12">
        <SectionHeader
          eyebrow="Category spotlight"
          title="Top stories by section"
          description="Provider sections keep browsing predictable; the ML classifier labels articles that arrive without one."
        />
        <div className="no-scrollbar mb-5 flex gap-2 overflow-x-auto pb-1">
          {categoryList.slice(0, 10).map((category) => (
            <button
              key={category.slug}
              type="button"
              onClick={() => setActiveCategory(category.slug)}
              className={cx('chip', activeCategory === category.slug && 'chip-active')}
              aria-pressed={activeCategory === category.slug}
            >
              {category.name}
              <span className="text-[10px] opacity-60">{category.article_count}</span>
            </button>
          ))}
        </div>

        {spotlight.loading ? (
          <SkeletonGrid count={3} />
        ) : spotlight.data?.results?.length ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {spotlight.data.results.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No stories in this section yet"
            message="Try another section, or search any topic to pull fresh reporting from the providers."
            action={
              <Link to={`/category/${activeCategory}`} className="btn-secondary">
                Open section
              </Link>
            }
          />
        )}
      </section>

      <section className="mt-12 grid gap-4 sm:grid-cols-3">
        {[
          {
            icon: Layers,
            title: 'Aggregated',
            body: 'Headlines from independent RSS feeds are normalized, deduplicated and linked back to the publisher.',
          },
          {
            icon: TrendingUp,
            title: 'Classified',
            body: 'TF-IDF plus logistic regression predicts a section, with confidence scores and editor corrections.',
          },
          {
            icon: ScanSearch,
            title: 'Annotated',
            body: 'Sentiment, extractive summaries and evidence lists make the context visible — never a verdict.',
          },
        ].map((item) => (
          <div key={item.title} className="rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
            <item.icon className="h-5 w-5 text-accent-600" aria-hidden />
            <h3 className="mt-3 text-base font-semibold">{item.title}</h3>
            <p className="mt-1.5 text-sm leading-6 text-ink-500 dark:text-ink-400">{item.body}</p>
          </div>
        ))}
      </section>

      <section className="mt-8 flex flex-col items-start justify-between gap-4 rounded-2xl border border-ink-200 bg-white p-6 dark:border-ink-800 dark:bg-ink-900 sm:flex-row sm:items-center">
        <div className="flex items-start gap-3">
          <Bookmark className="mt-0.5 h-5 w-5 text-ink-400" aria-hidden />
          <div>
            <h2 className="text-lg font-semibold">Build your own briefing</h2>
            <p className="mt-0.5 text-sm text-ink-500 dark:text-ink-400">
              Choose interests, save articles and get a feed ranked around what you read.
            </p>
          </div>
        </div>
        <Link to={user ? '/profile' : '/register'} className="btn-primary shrink-0">
          {user ? 'Manage interests' : 'Create an account'}
        </Link>
      </section>
    </div>
  );
}
