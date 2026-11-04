import { Newspaper, Server } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-ink-200 bg-white dark:border-ink-800 dark:bg-ink-900">
      <div className="container-page grid gap-10 py-12 md:grid-cols-4">
        <div className="md:col-span-2">
          <Link to="/" className="font-display text-2xl font-black tracking-tight">
            News<span className="text-accent-600 dark:text-accent-400">Hub</span>
          </Link>
          <p className="mt-3 max-w-md text-sm leading-6 text-ink-600 dark:text-ink-400">
            An intelligent news aggregator. NewsHub collects headlines and summaries
            from independent publishers, classifies them with machine learning, and
            links every story back to its original source.
          </p>
          <p className="mt-4 flex items-start gap-2 text-xs leading-5 text-ink-500 dark:text-ink-500">
            <Newspaper className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Article rights belong to the original publishers. Headlines, short
            descriptions and links are shown for discovery only.
          </p>
        </div>

        <div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-ink-500 dark:text-ink-400">
            Read
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-ink-700 dark:text-ink-300">
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/">Latest news</Link></li>
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/explore">Explore topics</Link></li>
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/categories">Categories</Link></li>
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/explore?sort=relevance">Trending</Link></li>
          </ul>
        </div>

        <div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-ink-500 dark:text-ink-400">
            Tools
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-ink-700 dark:text-ink-300">
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/fact-check">Fact check</Link></li>
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/saved">Saved articles</Link></li>
            <li><Link className="hover:text-accent-600 dark:hover:text-accent-400" to="/profile">Interests</Link></li>
            <li>
              <a
                className="inline-flex items-center gap-1 hover:text-accent-600 dark:hover:text-accent-400"
                href="/api/health/"
                target="_blank"
                rel="noreferrer noopener"
              >
                <Server className="h-3.5 w-3.5" /> API status
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-ink-200 py-5 dark:border-ink-800">
        <div className="container-page flex flex-col gap-2 text-xs text-ink-500 dark:text-ink-500 sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} NewsHub. A graduate portfolio project.</span>
          <span>
            Machine-learning predictions and AI summaries are informational, not
            verdicts. Always read the original reporting.
          </span>
        </div>
      </div>
    </footer>
  );
}
