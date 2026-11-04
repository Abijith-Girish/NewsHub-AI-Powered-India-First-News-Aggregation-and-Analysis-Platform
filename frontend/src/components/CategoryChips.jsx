import { Link } from 'react-router-dom';

import { cx } from '../lib/format';

export default function CategoryChips({
  categories = [],
  active,
  onSelect,
  includeAll = true,
  allLabel = 'All news',
  className = '',
}) {
  if (!categories.length) return null;

  if (onSelect) {
    return (
      <div className={cx('no-scrollbar flex items-center gap-2 overflow-x-auto pb-1', className)}>
        {includeAll && (
          <button
            type="button"
            onClick={() => onSelect('')}
            className={cx('chip', !active && 'chip-active')}
            aria-pressed={!active}
          >
            {allLabel}
          </button>
        )}
        {categories.map((category) => (
          <button
            key={category.slug}
            type="button"
            onClick={() => onSelect(category.slug)}
            className={cx('chip', active === category.slug && 'chip-active')}
            aria-pressed={active === category.slug}
          >
            {category.name}
            {category.article_count !== undefined && (
              <span className="text-[10px] opacity-60">{category.article_count}</span>
            )}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={cx('no-scrollbar flex items-center gap-2 overflow-x-auto pb-1', className)}>
      <Link to="/explore" className="chip">
        Browse all
      </Link>
      {categories.map((category) => (
        <Link key={category.slug} to={`/category/${category.slug}`} className="chip">
          {category.name}
          {category.article_count !== undefined && (
            <span className="text-[10px] opacity-60">{category.article_count}</span>
          )}
        </Link>
      ))}
    </div>
  );
}
