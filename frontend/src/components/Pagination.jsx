import { ChevronLeft, ChevronRight } from 'lucide-react';

import { cx } from '../lib/format';

function buildPages(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);
  const pages = new Set([1, total, current, current - 1, current + 1]);
  const sorted = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b);
  const withGaps = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) withGaps.push('…');
    withGaps.push(page);
  });
  return withGaps;
}

export default function Pagination({ page = 1, pages = 1, onChange, className = '' }) {
  if (!pages || pages <= 1) return null;
  const items = buildPages(page, pages);

  return (
    <nav className={cx('mt-8 flex items-center justify-center gap-1', className)} aria-label="Pagination">
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="btn-secondary btn-sm rounded-full p-2 disabled:opacity-40"
        aria-label="Previous page"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      {items.map((item, index) =>
        item === '…' ? (
          <span key={`gap-${index}`} className="px-2 text-sm text-ink-400">
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            onClick={() => onChange(item)}
            aria-current={item === page ? 'page' : undefined}
            className={cx(
              'h-9 min-w-9 rounded-full px-2 text-sm font-medium transition-colors',
              item === page
                ? 'bg-ink-900 text-white dark:bg-white dark:text-ink-900'
                : 'text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800'
            )}
          >
            {item}
          </button>
        )
      )}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= pages}
        className="btn-secondary btn-sm rounded-full p-2 disabled:opacity-40"
        aria-label="Next page"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </nav>
  );
}
