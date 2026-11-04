import { Compass, Home } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useDocumentTitle } from '../hooks/useDocumentTitle';

export default function NotFoundPage() {
  useDocumentTitle('Page not found');
  return (
    <div className="container-page flex min-h-[60vh] flex-col items-center justify-center py-16 text-center">
      <p className="font-display text-7xl font-black text-ink-200 dark:text-ink-800">404</p>
      <h1 className="mt-2 text-2xl font-bold">That page is not in the archive</h1>
      <p className="mt-2 max-w-md text-sm leading-6 text-ink-500 dark:text-ink-400">
        The link may be outdated, or the article may have been removed by its publisher.
        Try the latest feed or search for a topic.
      </p>
      <div className="mt-5 flex gap-2">
        <Link to="/" className="btn-primary"><Home className="h-4 w-4" /> Home</Link>
        <Link to="/explore" className="btn-secondary"><Compass className="h-4 w-4" /> Explore</Link>
      </div>
    </div>
  );
}
