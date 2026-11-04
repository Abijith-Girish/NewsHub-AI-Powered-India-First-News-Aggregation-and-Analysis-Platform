import { useEffect, useState } from 'react';
import { Activity, Bookmark, Clock3, Eye, RefreshCw } from 'lucide-react';
import ArticleCard from '../components/ArticleCard';
import { ErrorState } from '../components/States';
import { SkeletonLines } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiErrorMessage, newsApi } from '../lib/api';

function Stat({ icon: Icon, label, value }) {
  return <div className="card p-4"><Icon className="h-5 w-5 text-accent-600" /><p className="mt-3 text-2xl font-bold tabular-nums">{value}</p><p className="mt-1 text-xs text-ink-500">{label}</p></div>;
}

export default function AnalyticsPage() {
  useDocumentTitle('Reading analytics');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  async function load() {
    setLoading(true); setError('');
    try { const response = await newsApi.readingAnalytics(); setData(response.data); }
    catch (err) { setError(apiErrorMessage(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  return (
    <div className="container-page py-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="eyebrow">Personal dashboard · last 30 days</p><h1 className="mt-1 text-3xl font-bold">Reading analytics</h1><p className="mt-2 text-sm text-ink-500 dark:text-ink-400">Your reading activity is private to your account.</p></div>
        <button type="button" onClick={load} disabled={loading} className="btn-secondary btn-sm"><RefreshCw className="h-4 w-4" /> Refresh</button>
      </header>
      {loading && <div className="mt-7"><SkeletonLines count={8} /></div>}
      {error && <div className="mt-7"><ErrorState message={error} onRetry={load} /></div>}
      {data && (
        <>
          <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat icon={Eye} label="Article view events" value={data.total_article_views} />
            <Stat icon={Activity} label="Unique articles read" value={data.unique_articles_read} />
            <Stat icon={Clock3} label="Tracked reading minutes" value={data.reading_minutes} />
            <Stat icon={Bookmark} label="Saved articles" value={data.saved_articles} />
          </div>
          <div className="mt-7 grid gap-5 lg:grid-cols-2">
            <section className="card p-5"><h2 className="font-semibold">Topics you read</h2><div className="mt-4 space-y-3">{data.categories.length ? data.categories.map((item) => <div key={item.name}><div className="flex justify-between text-sm"><span>{item.name}</span><span className="tabular-nums text-ink-500">{item.count}</span></div><div className="mt-1 h-2 rounded-full bg-ink-100 dark:bg-ink-800"><div className="h-2 rounded-full bg-accent-600" style={{ width: `${Math.max(4, item.count / Math.max(...data.categories.map((row) => row.count)) * 100)}%` }} /></div></div>) : <p className="text-sm text-ink-500">Read a few articles to build your topic profile.</p>}</div></section>
            <section className="card p-5"><h2 className="font-semibold">Publishers you read</h2><div className="mt-4 divide-y divide-ink-100 dark:divide-ink-800">{data.publishers.length ? data.publishers.map((item) => <div key={item.name} className="flex justify-between py-2.5 text-sm"><span>{item.name}</span><span className="tabular-nums text-ink-500">{item.count} views</span></div>) : <p className="text-sm text-ink-500">No publisher activity recorded yet.</p>}</div></section>
          </div>
          <section className="mt-7"><h2 className="mb-4 text-xl font-bold">Most-read articles</h2>{data.top_articles.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{data.top_articles.map((article) => <ArticleCard key={article.id} article={article} />)}</div> : <p className="text-sm text-ink-500">Your most-read stories will appear here.</p>}</section>
        </>
      )}
    </div>
  );
}
