import { useEffect, useState } from 'react';
import { CalendarDays, Newspaper, RefreshCw, Sparkles } from 'lucide-react';
import ArticleCard from '../components/ArticleCard';
import { EmptyState, ErrorState } from '../components/States';
import { SkeletonGrid } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiErrorMessage, newsApi } from '../lib/api';

export default function DailyBriefingPage() {
  useDocumentTitle('AI daily briefing');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true); setError('');
    try { const response = await newsApi.briefing(); setData(response.data); }
    catch (err) { setError(apiErrorMessage(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  return (
    <div className="container-page py-8">
      <header className="mx-auto max-w-3xl text-center">
        <p className="eyebrow">Your daily read</p>
        <h1 className="mt-2 font-display text-3xl font-bold sm:text-4xl">AI Daily Briefing</h1>
        <p className="mt-2 text-sm leading-6 text-ink-500 dark:text-ink-400">A concise overview of recent reporting, with every story linked to its publisher.</p>
      </header>
      {data && (
        <section className="mx-auto mt-7 max-w-4xl rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900 sm:p-7">
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-500"><Sparkles className="h-4 w-4" /> Briefing summary</span>
            <span className="flex items-center gap-1 text-xs text-ink-400"><CalendarDays className="h-3.5 w-3.5" />{new Date(data.generated_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
          </div>
          <p className="mt-4 font-display text-lg leading-8">{data.intro}</p>
          <p className="mt-3 text-xs leading-5 text-ink-400">{data.note} {data.ai_generated ? 'AI-assisted summary.' : 'Deterministic summary; configure LLM_API_KEY for generated prose.'}</p>
        </section>
      )}
      <div className="mt-8 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-xl font-bold"><Newspaper className="h-5 w-5" /> Stories in this briefing</h2>
        <button type="button" onClick={load} disabled={loading} className="btn-secondary btn-sm"><RefreshCw className="h-4 w-4" /> Refresh</button>
      </div>
      {loading && <div className="mt-5"><SkeletonGrid count={6} /></div>}
      {error && <div className="mt-5"><ErrorState message={error} onRetry={load} /></div>}
      {!loading && !error && !data?.stories?.length && <div className="mt-5"><EmptyState title="No briefing available" message="Refresh the news feed and try again." /></div>}
      {!!data?.stories?.length && <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{data.stories.map((article, index) => <ArticleCard key={article.id} article={article} priority={index < 3} />)}</div>}
    </div>
  );
}
