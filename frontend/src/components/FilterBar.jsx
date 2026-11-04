import { Filter, X } from 'lucide-react';

import { cx } from '../lib/format';

const DATE_OPTIONS = [
  { value: 'all', label: 'Any time' },
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'This week' },
  { value: 'month', label: 'This month' },
];

const SORT_OPTIONS = [
  { value: 'relevance', label: 'Most relevant' },
  { value: 'latest', label: 'Latest first' },
  { value: 'oldest', label: 'Oldest first' },
];

export default function FilterBar({
  filters,
  onChange,
  sources = [],
  categories = [],
  onReset,
  showSort = true,
}) {
  const normalizedSources = sources.map((source) =>
    typeof source === 'string' ? source : source.name || source.source
  );

  function update(key, value) {
    onChange({ ...filters, [key]: value, page: 1 });
  }

  const hasFilters =
    (filters.category && filters.category !== 'all') ||
    (filters.source && filters.source !== 'all') ||
    (filters.date && filters.date !== 'all') ||
    filters.sort === 'oldest';

  return (
    <div className="card p-3.5">
      <div className="mb-2.5 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-ink-500">
          <Filter className="h-3.5 w-3.5" aria-hidden /> Filters
        </span>
        {hasFilters && onReset && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-accent-700 dark:hover:text-accent-300"
          >
            <X className="h-3 w-3" /> Reset
          </button>
        )}
      </div>
      <div className={cx('grid gap-2.5', showSort ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 sm:grid-cols-3')}>
        <label className="block">
          <span className="label">Category</span>
          <select
            className="select"
            value={filters.category || 'all'}
            onChange={(event) => update('category', event.target.value)}
          >
            <option value="all">All categories</option>
            {categories.map((category) => (
              <option key={category.slug} value={category.slug}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="label">Source</span>
          <select
            className="select"
            value={filters.source || 'all'}
            onChange={(event) => update('source', event.target.value)}
          >
            <option value="all">All sources</option>
            {normalizedSources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="label">Published</span>
          <select
            className="select"
            value={filters.date || 'all'}
            onChange={(event) => update('date', event.target.value)}
          >
            {DATE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {showSort && (
          <label className="block">
            <span className="label">Sort</span>
            <select
              className="select"
              value={filters.sort || 'relevance'}
              onChange={(event) => update('sort', event.target.value)}
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </div>
  );
}
