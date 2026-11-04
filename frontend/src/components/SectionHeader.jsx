import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function SectionHeader({ eyebrow, title, description, to, linkLabel = 'View all' }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h2 className="text-2xl font-bold tracking-tight sm:text-[1.7rem]">{title}</h2>
        {description && (
          <p className="mt-1 max-w-2xl text-sm leading-6 text-ink-500 dark:text-ink-400">
            {description}
          </p>
        )}
      </div>
      {to && (
        <Link
          to={to}
          className="inline-flex items-center gap-1 text-sm font-semibold text-ink-700 hover:text-accent-700 dark:text-ink-300 dark:hover:text-accent-300"
        >
          {linkLabel}
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      )}
    </div>
  );
}
