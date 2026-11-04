import { ExternalLink, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

import ArticleImage from './ArticleImage';
import SaveButton from './SaveButton';
import { cx, formatDateTime, timeAgo } from '../lib/format';

function Meta({ article, light = false }) {
  return (
    <div className={cx('flex flex-wrap items-center gap-x-2 gap-y-1 text-xs', light ? 'text-white/80' : 'meta')}>
      {article.source && (
        <span className="font-semibold uppercase tracking-wide">{article.source}</span>
      )}
      {article.source && <span aria-hidden>·</span>}
      <time dateTime={article.published_at} title={formatDateTime(article.published_at)}>
        {timeAgo(article.published_at)}
      </time>
      <a
        href={article.source_url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(event) => event.stopPropagation()}
        className={cx(
          'ml-0.5 inline-flex items-center gap-0.5 rounded-full px-1 py-0.5 transition-colors',
          light ? 'hover:bg-white/15' : 'hover:bg-ink-100 dark:hover:bg-ink-800'
        )}
        title="Open original article on the publisher's site"
        aria-label={`Open original article from ${article.source || 'publisher'}`}
      >
        <ExternalLink className="h-3 w-3" aria-hidden />
      </a>
    </div>
  );
}

function CategoryTag({ article }) {
  if (!article.category) return null;
  return (
    <Link
      to={`/category/${article.category.slug}`}
      className="eyebrow hover:text-accent-700 dark:hover:text-accent-300"
    >
      {article.category.name}
    </Link>
  );
}

function BreakingTag() {
  return (
    <span className="inline-flex items-center gap-1 rounded-sm bg-accent-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" aria-hidden />
      Breaking
    </span>
  );
}

export default function ArticleCard({ article, variant = 'default', priority = false, onSaveChange }) {
  if (!article) return null;

  if (variant === 'compact') {
    return (
      <article className="group flex gap-3 py-3">
        <Link
          to={`/article/${article.id}`}
          className="relative h-20 w-24 shrink-0 overflow-hidden rounded-lg"
          tabIndex={-1}
        >
          <ArticleImage
            src={article.image_url}
            alt=""
            category={article.category?.slug}
            className="h-full w-full transition-transform duration-300 group-hover:scale-105"
          />
        </Link>
        <div className="min-w-0 flex-1">
          <CategoryTag article={article} />
          <h3 className="mt-0.5 font-display text-[15px] font-semibold leading-snug text-ink-900 dark:text-ink-100">
            <Link to={`/article/${article.id}`} className="hover:text-accent-700 dark:hover:text-accent-300">
              {article.title}
            </Link>
          </h3>
          <div className="mt-1">
            <Meta article={article} />
          </div>
        </div>
      </article>
    );
  }

  if (variant === 'hero') {
    return (
      <article className="group relative overflow-hidden rounded-2xl bg-ink-900 text-white shadow-card">
        <Link to={`/article/${article.id}`} className="block">
          <div className="relative aspect-[16/10] w-full sm:aspect-[16/9]">
            <ArticleImage
              src={article.image_url}
              alt={article.title}
              category={article.category?.slug}
              className="h-full w-full object-cover opacity-90 transition-transform duration-500 group-hover:scale-[1.02]"
              priority={priority}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/55 to-transparent" />
            <div className="absolute inset-x-0 bottom-0 p-5 sm:p-7">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {article.is_breaking && <BreakingTag />}
                {article.category && (
                  <span className="rounded-full border border-white/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white/90">
                    {article.category.name}
                  </span>
                )}
              </div>
              <h2 className="max-w-2xl text-balance font-display text-2xl font-bold leading-tight sm:text-3xl lg:text-4xl">
                {article.title}
              </h2>
              {article.description && (
                <p className="mt-2 line-clamp-2 max-w-2xl text-sm leading-6 text-white/80">
                  {article.description}
                </p>
              )}
              <div className="mt-3">
                <Meta article={article} light />
              </div>
            </div>
          </div>
        </Link>
        <div className="absolute right-4 top-4">
          <SaveButton article={article} onChange={onSaveChange} />
        </div>
      </article>
    );
  }

  return (
    <article className="card group flex h-full flex-col overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift">
      <div className="relative">
        <Link to={`/article/${article.id}`} className="block aspect-[16/9] overflow-hidden" tabIndex={-1}>
          <ArticleImage
            src={article.image_url}
            alt={article.title}
            category={article.category?.slug}
            className="h-full w-full transition-transform duration-500 group-hover:scale-[1.03]"
            priority={priority}
          />
        </Link>
        <div className="absolute right-2.5 top-2.5">
          <SaveButton article={article} onChange={onSaveChange} />
        </div>
        {article.is_breaking && (
          <div className="absolute left-2.5 top-2.5">
            <BreakingTag />
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-5">
        <CategoryTag article={article} />
        <h3 className="font-display text-lg font-semibold leading-snug text-ink-900 dark:text-ink-100">
          <Link
            to={`/article/${article.id}`}
            className="transition-colors hover:text-accent-700 dark:hover:text-accent-300"
          >
            {article.title}
          </Link>
        </h3>
        {article.description && (
          <p className="line-clamp-3 text-sm leading-6 text-ink-600 dark:text-ink-400">
            {article.description}
          </p>
        )}
        {article.match_reason && (
          <p className="mt-auto inline-flex items-center gap-1 pt-1 text-[11px] font-medium text-signal-600 dark:text-teal-300">
            <Sparkles className="h-3 w-3" aria-hidden />
            {article.match_reason}
          </p>
        )}
        <div className={cx('mt-auto pt-2', article.match_reason && 'mt-0')}>
          <Meta article={article} />
        </div>
      </div>
    </article>
  );
}
