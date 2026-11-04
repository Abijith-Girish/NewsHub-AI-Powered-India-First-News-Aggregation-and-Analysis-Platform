import { Bookmark, Compass } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import ArticleCard from '../components/ArticleCard';
import { SkeletonGrid } from '../components/Skeletons';
import { EmptyState, ErrorState } from '../components/States';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { newsApi } from '../lib/api';

export default function SavedPage() {
  useDocumentTitle('Saved articles');
  const [items, setItems] = useState([]);

  const saved = useFetch(() => newsApi.saved().then((res) => res.data.results), []);

  useEffect(() => {
    if (saved.data) setItems(saved.data);
  }, [saved.data]);

  function handleSaveChange(articleId, isSaved) {
    if (!isSaved) {
      setItems((current) => current.filter((article) => article.id !== articleId));
    }
  }

  return (
    <div className="container-page py-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-ink-200 pb-6 dark:border-ink-800">
        <div>
          <p className="eyebrow">Reading list</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">Saved articles</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-500 dark:text-ink-400">
            Everything you bookmarked, newest first. Saved stories also shape your
            personalized recommendations.
          </p>
        </div>
        <Link to="/explore" className="btn-secondary btn-sm">
          <Compass className="h-3.5 w-3.5" /> Find more news
        </Link>
      </header>

      <div className="mt-6">
        {saved.loading && <SkeletonGrid count={3} />}
        {saved.error && <ErrorState message={saved.error} onRetry={saved.reload} />}
        {!saved.loading && !saved.error && !items.length && (
          <EmptyState
            icon={Bookmark}
            title="Your reading list is empty"
            message="Use the bookmark button on any article to keep it here for later."
            action={<Link to="/explore" className="btn-primary">Browse news</Link>}
          />
        )}
        {items.length > 0 && (
          <>
            <p className="mb-4 text-xs text-ink-500">
              {items.length} saved article{items.length === 1 ? '' : 's'}
            </p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((article) => (
                <ArticleCard
                  key={article.id}
                  article={{ ...article, saved: true }}
                  onSaveChange={(isSaved) => handleSaveChange(article.id, isSaved)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
