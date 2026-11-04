import { Flame, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';

import ArticleCard from './ArticleCard';
import { SkeletonLines } from './Skeletons';

export default function TrendingRail({ data, loading, compactStories = 4 }) {
  const topics = data?.topics || [];
  const stories = data?.stories || [];

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
        <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider">
          <TrendingUp className="h-4 w-4 text-accent-600" aria-hidden />
          Trending now
        </h2>
        <Link to="/explore" className="text-xs font-medium text-ink-500 hover:text-ink-900 dark:hover:text-white">
          Explore
        </Link>
      </div>

      <div className="p-5">
        {loading ? (
          <SkeletonLines count={5} />
        ) : topics.length ? (
          <div className="flex flex-wrap gap-2">
            {topics.slice(0, 8).map((topic, index) => (
              <Link
                key={topic.topic}
                to={`/explore?q=${encodeURIComponent(topic.topic)}`}
                className="group inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-ink-50 px-2.5 py-1 text-xs text-ink-700 transition-colors hover:border-accent-300 hover:bg-accent-50 hover:text-accent-800 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:border-accent-800 dark:hover:bg-accent-950/40 dark:hover:text-accent-200"
              >
                {index === 0 && <Flame className="h-3 w-3 text-accent-600" aria-hidden />}
                <span className="font-medium">{topic.topic}</span>
                <span className="text-[10px] opacity-60">{topic.article_count}</span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-500">Trending topics appear once enough articles are stored.</p>
        )}
      </div>

      {stories.length > 0 && (
        <div className="border-t border-ink-100 px-5 py-2 dark:border-ink-800">
          <h3 className="mt-2 text-[11px] font-bold uppercase tracking-widest text-ink-400">
            Most engaged stories
          </h3>
          <div className="divide-y divide-ink-100 dark:divide-ink-800">
            {stories.slice(0, compactStories).map((article) => (
              <ArticleCard key={article.id} article={article} variant="compact" />
            ))}
          </div>
        </div>
      )}

      {data?.note && (
        <p className="border-t border-ink-100 px-5 py-3 text-[11px] leading-4 text-ink-400 dark:border-ink-800 dark:text-ink-500">
          {data.note}
        </p>
      )}
    </div>
  );
}
