import { ArrowUpRight, LayoutGrid } from 'lucide-react';
import { Link } from 'react-router-dom';

import { SkeletonGrid } from '../components/Skeletons';
import { ErrorState } from '../components/States';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { newsApi } from '../lib/api';

const ACCENTS = [
  'from-sky-500 to-indigo-600',
  'from-indigo-500 to-violet-600',
  'from-stone-500 to-ink-700',
  'from-teal-500 to-emerald-700',
  'from-emerald-500 to-green-700',
  'from-fuchsia-500 to-pink-600',
  'from-rose-500 to-red-700',
  'from-amber-500 to-orange-600',
  'from-cyan-500 to-sky-700',
  'from-slate-500 to-slate-700',
];

export default function CategoriesPage() {
  useDocumentTitle('Categories');
  const categories = useFetch(() => newsApi.categories().then((res) => res.data.results), []);
  const list = categories.data || [];
  const total = list.reduce((sum, category) => sum + (category.article_count || 0), 0);

  return (
    <div className="container-page py-10">
      <header className="max-w-3xl">
        <p className="eyebrow">Sections</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">Browse by category</h1>
        <p className="mt-2 text-sm leading-6 text-ink-500 dark:text-ink-400">
          Ten editorial sections covering {total.toLocaleString()} published stories currently
          stored by NewsHub. Provider sections are preserved; the classifier fills the gaps.
        </p>
      </header>

      <div className="mt-8">
        {categories.loading && <SkeletonGrid count={6} />}
        {categories.error && <ErrorState message={categories.error} onRetry={categories.reload} />}
        {!categories.loading && !categories.error && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((category, index) => (
              <Link
                key={category.slug}
                to={`/category/${category.slug}`}
                className="group relative overflow-hidden rounded-2xl border border-ink-200 bg-white p-5 transition-all hover:-translate-y-0.5 hover:shadow-lift dark:border-ink-800 dark:bg-ink-900"
              >
                <div
                  className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${ACCENTS[index % ACCENTS.length]}`}
                  aria-hidden
                />
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-display text-xl font-bold">{category.name}</h2>
                  <ArrowUpRight className="h-4 w-4 text-ink-400 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden />
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-ink-500 dark:text-ink-400">
                  {category.description || 'Latest coverage in this section.'}
                </p>
                <p className="mt-4 inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  <LayoutGrid className="h-3 w-3" aria-hidden />
                  {category.article_count} article{category.article_count === 1 ? '' : 's'}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
