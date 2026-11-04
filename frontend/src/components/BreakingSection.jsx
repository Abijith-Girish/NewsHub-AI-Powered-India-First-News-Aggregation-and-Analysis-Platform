import { Radio } from 'lucide-react';

import ArticleCard from './ArticleCard';
import { NoteBanner } from './States';
import { SkeletonCard } from './Skeletons';

export default function BreakingSection({ data, loading }) {
  const articles = data?.results || [];

  if (loading) {
    return (
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="card overflow-hidden">
            <div className="skeleton aspect-[16/9] rounded-none" />
            <div className="space-y-3 p-6">
              <div className="skeleton h-4 w-32" />
              <div className="skeleton h-7 w-11/12" />
              <div className="skeleton h-7 w-2/3" />
            </div>
          </div>
        </div>
        <div className="space-y-4 rounded-2xl border border-ink-200 p-4 dark:border-ink-800">
          {[0, 1, 2].map((item) => (
            <SkeletonCard key={item} compact />
          ))}
        </div>
      </div>
    );
  }

  if (!articles.length) return null;

  const [lead, ...rest] = articles;

  return (
    <section aria-labelledby="breaking-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            {!data.fallback && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-500 opacity-70" />
            )}
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-600" />
          </span>
          <h2
            id="breaking-heading"
            className="text-xs font-bold uppercase tracking-[0.18em] text-accent-700 dark:text-accent-400"
          >
            {data.fallback ? 'Latest headlines' : 'Breaking now'}
          </h2>
        </div>
        <span className="inline-flex items-center gap-1 text-[11px] text-ink-400 dark:text-ink-500">
          <Radio className="h-3.5 w-3.5" aria-hidden />
          Provider-flagged, last 24 hours
        </span>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ArticleCard article={lead} variant="hero" priority />
        </div>
        <div className="rounded-2xl border border-ink-200 bg-white p-2 dark:border-ink-800 dark:bg-ink-900">
          {rest.length ? (
            <div className="divide-y divide-ink-100 px-2 dark:divide-ink-800">
              {rest.slice(0, 4).map((article) => (
                <ArticleCard key={article.id} article={article} variant="compact" />
              ))}
            </div>
          ) : (
            <p className="px-4 py-8 text-sm text-ink-500">
              More headlines will appear here as publishers update their feeds.
            </p>
          )}
        </div>
      </div>

      {data.fallback && data.note && (
        <div className="mt-4">
          <NoteBanner>{data.note}</NoteBanner>
        </div>
      )}
    </section>
  );
}
