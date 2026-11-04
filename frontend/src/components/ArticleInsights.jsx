import { useEffect, useState } from 'react';
import { ExternalLink, GitCompareArrows, LoaderCircle, RefreshCw, Route, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

import { apiErrorMessage, newsApi } from '../lib/api';
import { formatDateTime } from '../lib/format';

export function NewsLensPanel({ articleId }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const { data } = await newsApi.newsLens(articleId);
      setPayload(data);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [articleId]);

  return (
    <section className="mt-8 rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">NewsLens</p>
          <h2 className="mt-1 flex items-center gap-2 text-lg font-bold"><GitCompareArrows className="h-5 w-5" /> Multi-source perspective</h2>
          <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">Compare how other publishers cover this story.</p>
        </div>
        <button type="button" onClick={load} disabled={loading} className="btn-secondary btn-sm">
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Refresh
        </button>
      </div>
      {loading && <p className="mt-4 text-sm text-ink-500">Finding related coverage…</p>}
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      {!loading && payload && !payload.comparisons?.length && (
        <p className="mt-4 rounded-xl bg-ink-50 p-3 text-sm text-ink-500 dark:bg-ink-800">No sufficiently similar coverage from another publisher is currently stored. Try again after the next news refresh.</p>
      )}
      {!!payload?.comparisons?.length && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {payload.comparisons.map((item) => (
            <article key={item.article.id} className="rounded-xl border border-ink-200 p-4 dark:border-ink-700">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500">
                <span className="font-semibold">{item.article.source || 'Publisher'}</span>
                <span>{Math.round(item.similarity * 100)}% match score</span>
              </div>
              <p className="mt-1 text-[11px] text-ink-400">Wording tone: {item.tone || 'not assessed'}</p>
              <Link to={`/article/${item.article.id}`} className="mt-2 block font-semibold leading-6 hover:text-accent-700 dark:hover:text-accent-300">{item.article.title}</Link>
              {item.article.description && <p className="mt-2 line-clamp-3 text-sm leading-6 text-ink-500 dark:text-ink-400">{item.article.description}</p>}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {item.shared_topics?.map((term) => <span key={`s-${term}`} className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">Shared: {term}</span>)}
                {item.distinctive_terms?.map((term) => <span key={`d-${term}`} className="rounded-full bg-amber-50 px-2 py-1 text-[10px] text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">Focus: {term}</span>)}
              </div>
              <a href={item.article.source_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-accent-700 dark:text-accent-300">Original report <ExternalLink className="h-3 w-3" /></a>
            </article>
          ))}
        </div>
      )}
      {payload?.note && <p className="mt-4 text-xs leading-5 text-ink-400">{payload.note}</p>}
    </section>
  );
}

export function TruthTracePanel({ article, isAuthenticated }) {
  const [tracked, setTracked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function startTracking() {
    setBusy(true);
    setError('');
    try {
      const { data } = await newsApi.trackClaim({ article_id: article.id, claim: article.title });
      setTracked(data);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-5 rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
      <p className="eyebrow">TruthTrace</p>
      <h2 className="mt-1 flex items-center gap-2 text-lg font-bold"><Route className="h-5 w-5" /> Claim evolution timeline</h2>
      <p className="mt-1 text-sm leading-6 text-ink-500 dark:text-ink-400">Follow this headline and collect related reports as new articles enter NewsHub.</p>
      {!isAuthenticated ? (
        <Link to="/login" className="btn-secondary btn-sm mt-4">Sign in to track this story</Link>
      ) : tracked ? (
        <Link to="/truth-trace" className="btn-secondary btn-sm mt-4">View tracked timeline</Link>
      ) : (
        <button type="button" onClick={startTracking} disabled={busy} className="btn-primary btn-sm mt-4">
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Track this claim
        </button>
      )}
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      {tracked && (
        <div className="mt-5 border-l-2 border-accent-500 pl-4">
          <p className="text-sm font-semibold">Tracking: {tracked.claim}</p>
          <p className="mt-1 text-xs text-ink-500">{tracked.evidence?.length || 0} related reports collected</p>
          {tracked.evidence?.length ? (
            <ol className="mt-3 space-y-3">
              {tracked.evidence.map((item) => (
                <li key={item.id} className="relative">
                  <p className="text-[11px] text-ink-400">{formatDateTime(item.article.published_at)}</p>
                  <Link to={`/article/${item.article.id}`} className="mt-0.5 block text-sm font-medium hover:text-accent-700 dark:hover:text-accent-300">{item.article.title}</Link>
                  <p className="mt-1 text-xs text-ink-500">{item.article.source || 'Publisher'} · related context</p>
                </li>
              ))}
            </ol>
          ) : <p className="mt-3 text-sm text-ink-500">No related reports found yet. Reopen this tracked claim later to refresh the timeline.</p>}
          <p className="mt-3 text-xs leading-5 text-ink-400">Related reports are not automatically treated as proof for or against the claim.</p>
        </div>
      )}
    </section>
  );
}
