import { ChevronRight, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import ArticleCard from '../components/ArticleCard';
import Pagination from '../components/Pagination';
import { SkeletonGrid } from '../components/Skeletons';
import { EmptyState, ErrorState } from '../components/States';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { newsApi } from '../lib/api';

export default function CategoryPage() {
  const { slug } = useParams();
  const [page, setPage] = useState(1);
  const [categoryName, setCategoryName] = useState('');

  const result = useFetch(
    () => newsApi.articlesByCategory(slug, { page, page_size: 18 }).then((res) => res.data),
    [slug, page]
  );

  useEffect(() => {
    setPage(1);
  }, [slug]);

  useEffect(() => {
    if (result.data?.category?.name) setCategoryName(result.data.category.name);
  }, [result.data]);

  useDocumentTitle(categoryName || 'Category');

  const articles = result.data?.results || [];
  const category = result.data?.category;

  return (
    <div className="container-page py-8">
      <nav className="flex items-center gap-1.5 text-xs text-ink-500" aria-label="Breadcrumb">
        <Link to="/" className="hover:text-ink-900 dark:hover:text-white">Home</Link>
        <ChevronRight className="h-3 w-3" aria-hidden />
        <Link to="/categories" className="hover:text-ink-900 dark:hover:text-white">Categories</Link>
        <ChevronRight className="h-3 w-3" aria-hidden />
        <span className="text-ink-800 dark:text-ink-200">{categoryName || slug}</span>
      </nav>

      <header className="mt-4 flex flex-wrap items-end justify-between gap-4 border-b border-ink-200 pb-6 dark:border-ink-800">
        <div>
          <p className="eyebrow">Section</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">
            {categoryName || slug?.replace(/-/g, ' ')}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-500 dark:text-ink-400">
            {category?.description ||
              'Latest reporting filed under this section, ordered by publication time.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to={`/explore?category=${slug}`} className="btn-secondary btn-sm">
            <Search className="h-3.5 w-3.5" /> Search this section
          </Link>
        </div>
      </header>

      <div className="mt-6">
        {result.loading && <SkeletonGrid count={6} />}
        {result.error && <ErrorState message={result.error} onRetry={result.reload} />}
        {!result.loading && !result.error && !articles.length && (
          <EmptyState
            title="No articles in this section yet"
            message="The providers have not returned stories for this category. Try another section or run a topic search."
            action={<Link to="/categories" className="btn-primary">Browse categories</Link>}
          />
        )}
        {articles.length > 0 && (
          <>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {articles.map((article, index) => (
                <ArticleCard key={article.id} article={article} priority={index < 3} />
              ))}
            </div>
            <Pagination page={result.data?.page || 1} pages={result.data?.pages || 1} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
