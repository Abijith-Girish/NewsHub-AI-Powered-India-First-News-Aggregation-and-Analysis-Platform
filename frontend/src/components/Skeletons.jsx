import { cx } from '../lib/format';

export function SkeletonCard({ compact = false }) {
  if (compact) {
    return (
      <div className="flex gap-3 py-3">
        <div className="skeleton h-16 w-20 shrink-0" />
        <div className="flex-1 space-y-2 py-0.5">
          <div className="skeleton h-3 w-16" />
          <div className="skeleton h-4 w-full" />
          <div className="skeleton h-3 w-24" />
        </div>
      </div>
    );
  }
  return (
    <article className="card overflow-hidden">
      <div className="skeleton aspect-[16/9] rounded-none" />
      <div className="space-y-3 p-5">
        <div className="skeleton h-3 w-20" />
        <div className="skeleton h-5 w-11/12" />
        <div className="skeleton h-5 w-3/4" />
        <div className="space-y-2 pt-1">
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-2/3" />
        </div>
        <div className="flex justify-between pt-3">
          <div className="skeleton h-3 w-24" />
          <div className="skeleton h-3 w-16" />
        </div>
      </div>
    </article>
  );
}

export function SkeletonGrid({ count = 6, columns = 'sm:grid-cols-2 lg:grid-cols-3' }) {
  return (
    <div className={cx('grid gap-5', columns)}>
      {Array.from({ length: count }).map((_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  );
}

export function SkeletonLines({ count = 4 }) {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="skeleton h-3.5" style={{ width: `${92 - index * 8}%` }} />
      ))}
    </div>
  );
}
