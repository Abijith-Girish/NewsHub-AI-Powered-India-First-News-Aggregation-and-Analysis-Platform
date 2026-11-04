import { useEffect, useState } from 'react';
import { ExternalLink, RefreshCw, Route, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState } from '../components/States';
import { SkeletonLines } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiErrorMessage, newsApi } from '../lib/api';
import { formatDateTime } from '../lib/format';

export default function TruthTracePage() {
  useDocumentTitle('TruthTrace · tracked claims');
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  async function load() {
    setLoading(true); setError('');
    try { const { data } = await newsApi.trackedClaims(); setClaims(data.results || []); }
    catch (err) { setError(apiErrorMessage(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function refreshClaim(id) {
    setBusyId(id);
    try {
      const { data } = await newsApi.trackedClaim(id);
      setClaims((current) => current.map((item) => item.id === id ? data : item));
    } catch (err) { setError(apiErrorMessage(err)); }
    finally { setBusyId(null); }
  }

  async function removeClaim(id) {
    setBusyId(id);
    try { await newsApi.deleteTrackedClaim(id); setClaims((current) => current.filter((item) => item.id !== id)); }
    catch (err) { setError(apiErrorMessage(err)); }
    finally { setBusyId(null); }
  }

  return (
    <div className="container-page py-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="eyebrow">Evidence timeline</p><h1 className="mt-1 flex items-center gap-2 text-3xl font-bold"><Route className="h-7 w-7" /> TruthTrace</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-ink-500 dark:text-ink-400">Revisit claims you are following and refresh their timelines as new related articles are ingested.</p></div>
        <button type="button" onClick={load} disabled={loading} className="btn-secondary btn-sm"><RefreshCw className="h-4 w-4" /> Refresh list</button>
      </header>
      {loading && <div className="mt-7"><SkeletonLines count={8} /></div>}
      {error && <div className="mt-7"><ErrorState message={error} onRetry={load} /></div>}
      {!loading && !error && !claims.length && <div className="mt-7"><EmptyState title="No tracked claims yet" message="Open any article and select Track this claim to start a timeline." action={<Link to="/explore" className="btn-primary btn-sm">Explore news</Link>} /></div>}
      <div className="mt-6 space-y-4">
        {claims.map((claim) => (
          <section key={claim.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1"><p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Tracking since {formatDateTime(claim.created_at)}</p><h2 className="mt-1 font-semibold leading-6">{claim.claim}</h2><p className="mt-1 text-xs text-ink-500">{claim.evidence?.length || 0} related reports in timeline</p></div>
              <div className="flex gap-2"><button type="button" disabled={busyId === claim.id} onClick={() => refreshClaim(claim.id)} className="btn-secondary btn-sm"><RefreshCw className="h-3.5 w-3.5" /> Update</button><button type="button" disabled={busyId === claim.id} onClick={() => removeClaim(claim.id)} className="btn-secondary btn-sm" aria-label="Delete tracked claim"><Trash2 className="h-3.5 w-3.5" /></button></div>
            </div>
            {!!claim.evidence?.length ? (
              <ol className="mt-5 space-y-4 border-l-2 border-ink-200 pl-4 dark:border-ink-700">
                {claim.evidence.map((item) => <li key={item.id}><p className="text-[11px] text-ink-400">{formatDateTime(item.article.published_at)}</p><Link to={`/article/${item.article.id}`} className="mt-1 block text-sm font-semibold hover:text-accent-700 dark:hover:text-accent-300">{item.article.title}</Link><p className="mt-1 text-xs text-ink-500">{item.article.source || 'Publisher'} · related context</p><a href={item.article.source_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-[11px] text-accent-700 dark:text-accent-300">Original report <ExternalLink className="h-3 w-3" /></a></li>)}
              </ol>
            ) : <p className="mt-4 text-sm text-ink-500">No related reports have been found yet. Update the timeline after more news arrives.</p>}
            <p className="mt-4 text-xs leading-5 text-ink-400">Related reports are collected as context; NewsHub does not automatically classify them as proof for or against this claim.</p>
          </section>
        ))}
      </div>
    </div>
  );
}
