import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ExternalLink,
  History,
  Loader2,
  Scale,
  ScanSearch,
  ShieldQuestion,
  XCircle,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { NoteBanner } from '../components/States';
import { useAuth } from '../context/AuthContext';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { factCheckApi, apiErrorMessage } from '../lib/api';
import { VERDICT_STYLES, cx, formatDateTime, percent, timeAgo } from '../lib/format';

const EXAMPLES = [
  {
    label: 'Policy claim',
    claim: 'The European Central Bank raised interest rates at its most recent meeting',
  },
  {
    label: 'Health claim',
    claim: 'The World Health Organization declared the mpox outbreak a public health emergency',
  },
];

const STANCE_STYLES = {
  supporting: {
    label: 'Supporting',
    className:
      'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200',
    icon: CheckCircle2,
  },
  contradicting: {
    label: 'Contradicting',
    className:
      'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200',
    icon: XCircle,
  },
  context: {
    label: 'Related context',
    className:
      'border-ink-200 bg-ink-100 text-ink-700 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-300',
    icon: CircleHelp,
  },
  weak: {
    label: 'Weak link',
    className:
      'border-ink-200 bg-white text-ink-500 dark:border-ink-700 dark:bg-ink-900 dark:text-ink-400',
    icon: CircleHelp,
  },
};

function ResultPanel({ result, onReset }) {
  const style = VERDICT_STYLES[result.verdict] || VERDICT_STYLES.insufficient;
  const confidence = Math.round((result.confidence || 0) * 100);
  const supporting = (result.evidence || []).filter((item) => item.stance === 'supporting').length;
  const contradicting = (result.evidence || []).filter((item) => item.stance === 'contradicting').length;

  return (
    <section className="animate-fade-in space-y-5" aria-label="Fact check result">
      <div className={cx('rounded-2xl border p-5 sm:p-6', style.tone)}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] opacity-70">
              Automated assessment
            </p>
            <h2 className="mt-1 font-display text-2xl font-bold">{result.verdict_label || style.label}</h2>
          </div>
          <div className="text-right">
            <p className="text-[11px] uppercase tracking-wider opacity-70">Confidence</p>
            <p className="font-display text-2xl font-bold">{confidence}%</p>
          </div>
        </div>

        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/60 dark:bg-black/30">
          <div className={cx('h-full rounded-full transition-all', style.bar)} style={{ width: `${confidence}%` }} />
        </div>

        <div className="mt-4 grid gap-2 text-xs sm:grid-cols-3">
          <span className="rounded-lg bg-white/60 px-3 py-2 dark:bg-black/20">
            {supporting} supporting item{supporting === 1 ? '' : 's'}
          </span>
          <span className="rounded-lg bg-white/60 px-3 py-2 dark:bg-black/20">
            {contradicting} contradicting item{contradicting === 1 ? '' : 's'}
          </span>
          <span className="rounded-lg bg-white/60 px-3 py-2 dark:bg-black/20">
            {(result.evidence || []).length} evidence link{(result.evidence || []).length === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      <div className="card p-5">
        <p className="text-[11px] font-bold uppercase tracking-widest text-ink-400">Submitted claim</p>
        <p className="mt-2 font-display text-lg leading-7">“{result.claim}”</p>
        {result.article_title && result.article_title !== result.claim && (
          <p className="mt-2 text-sm text-ink-500">Headline: {result.article_title}</p>
        )}
        {result.source_url && (
          <a
            href={result.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 break-all text-xs text-ink-500 underline hover:text-ink-900 dark:hover:text-white"
          >
            {result.source_url} <ExternalLink className="h-3 w-3 shrink-0" />
          </a>
        )}
        <p className="mt-3 text-[11px] text-ink-400">
          Analysed {formatDateTime(result.created_at)} · engine: {result.engine}
        </p>
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-widest text-ink-500">Explanation</h3>
          <span className="rounded-full border border-signal-500/30 bg-signal-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-600 dark:text-teal-300">
            AI-assisted text
          </span>
        </div>
        <p className="mt-3 text-sm leading-7 text-ink-700 dark:text-ink-300">{result.explanation}</p>
        <p className="mt-3 text-[11px] leading-5 text-ink-400">
          The label is produced by conservative rule-based scoring over retrieved evidence.
          When an LLM is configured it only writes this explanation — it cannot change the
          verdict.
        </p>
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
          <h3 className="text-sm font-bold uppercase tracking-widest text-ink-500">
            Evidence used ({(result.evidence || []).length})
          </h3>
        </div>
        {(result.evidence || []).length ? (
          <ul className="divide-y divide-ink-100 dark:divide-ink-800">
            {result.evidence.map((item) => {
              const stance = STANCE_STYLES[item.stance] || STANCE_STYLES.weak;
              const Icon = stance.icon;
              return (
                <li key={item.url} className="p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider', stance.className)}>
                      <Icon className="h-3 w-3" aria-hidden /> {stance.label}
                    </span>
                    <span className="text-[11px] text-ink-500">
                      {item.source || 'Unknown source'}
                      {item.published_at ? ` · ${timeAgo(item.published_at)}` : ''}
                    </span>
                    {item.trusted && (
                      <span className="rounded-full bg-signal-500/10 px-2 py-0.5 text-[10px] font-medium text-signal-600 dark:text-teal-300">
                        Established publisher
                      </span>
                    )}
                    {typeof item.coverage === 'number' && (
                      <span className="text-[10px] text-ink-400">
                        claim-term coverage {Math.round(item.coverage * 100)}%
                      </span>
                    )}
                  </div>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 block font-display text-base font-semibold leading-snug hover:text-accent-700 dark:hover:text-accent-300"
                  >
                    {item.title} <ArrowUpRight className="inline h-3.5 w-3.5" />
                  </a>
                  {item.excerpt && (
                    <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-ink-500 dark:text-ink-400">
                      {item.excerpt}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="p-5 text-sm text-ink-500">
            No related coverage was retrieved. That means the search found nothing it could
            use — not that the claim is true or false.
          </p>
        )}
      </div>

      {(result.related_articles || []).length > 0 && (
        <div className="card p-5">
          <h3 className="text-sm font-bold uppercase tracking-widest text-ink-500">
            Related stories in NewsHub
          </h3>
          <ul className="mt-3 space-y-2">
            {result.related_articles.map((article) => (
              <li key={article.url}>
                <Link
                  to={`/article/${article.id}`}
                  className="flex items-start justify-between gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-ink-50 dark:hover:bg-ink-800"
                >
                  <span>
                    {article.title}
                    <span className="ml-1.5 text-[11px] text-ink-400">{article.source}</span>
                  </span>
                  <ArrowUpRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="card group p-5">
        <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-bold uppercase tracking-widest text-ink-500">
          Method and limitations
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-4 space-y-3 text-xs leading-6 text-ink-600 dark:text-ink-400">
          <p>{result.analysis_notes?.method}</p>
          {result.analysis_notes?.queries && (
            <p>
              <span className="font-semibold">Search queries:</span>{' '}
              {result.analysis_notes.queries.join(' · ')}
            </p>
          )}
          <p>
            <span className="font-semibold">Providers:</span>{' '}
            {result.analysis_notes?.providers_succeeded ?? 0}/
            {result.analysis_notes?.providers_attempted ?? 0} reachable this run
          </p>
          {result.analysis_notes?.limitations && (
            <ul className="list-disc space-y-1 pl-5">
              {result.analysis_notes.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          )}
        </div>
      </details>

      <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div>
          <p className="font-semibold">This is not a definitive verdict.</p>
          <p className="mt-1">{result.disclaimer}</p>
        </div>
      </div>

      <button type="button" onClick={onReset} className="btn-secondary">
        <ScanSearch className="h-4 w-4" /> Analyse another claim
      </button>
    </section>
  );
}

export default function FactCheckPage() {
  useDocumentTitle('Fact check');
  const location = useLocation();
  const { user } = useAuth();
  const resultRef = useRef(null);
  const prefill = location.state || {};

  const [form, setForm] = useState({
    claim: prefill.claim || '',
    article_title: prefill.article_title || '',
    source_url: prefill.source_url || '',
    content: '',
  });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setForm((current) => ({
      ...current,
      claim: prefill.claim || current.claim,
      article_title: prefill.article_title || current.article_title,
      source_url: prefill.source_url || current.source_url,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill.claim, prefill.article_title, prefill.source_url]);

  const history = useFetch(
    () => (user ? factCheckApi.history().then((res) => res.data.results) : Promise.resolve([])),
    [user?.id]
  );

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (![form.claim, form.article_title, form.source_url, form.content].some((value) => value.trim())) {
      setError('Enter a claim, a headline, an article URL or a paragraph to analyse.');
      return;
    }
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const { data } = await factCheckApi.analyze(form);
      setResult(data);
      history.reload();
      window.setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 120);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadHistory(entry) {
    try {
      const { data } = await factCheckApi.detail(entry.id);
      setResult(data);
      window.setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 120);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <div className="container-page py-8">
      <header className="max-w-3xl">
        <p className="eyebrow">News literacy</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">Fact check a claim</h1>
        <p className="mt-2 text-sm leading-6 text-ink-500 dark:text-ink-400">
          NewsHub searches independent coverage and fact-check reporting, labels each item as
          supporting, contradicting or context, and shows every source it used. It will say
          “insufficient evidence” when that is the honest answer.
        </p>
      </header>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <form onSubmit={submit} className="card space-y-4 p-5 sm:p-6">
            <div>
              <label className="label" htmlFor="claim">Claim to check</label>
              <textarea
                id="claim"
                rows={4}
                value={form.claim}
                onChange={(event) => update('claim', event.target.value)}
                placeholder="Paste a claim, quote or the sentence you want to verify…"
                className="input resize-y"
                maxLength={2000}
              />
              <p className="mt-1 text-[11px] text-ink-400">
                {form.claim.length}/2000 characters. Only the first two sentences are treated
                as the core claim.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="headline">Article headline (optional)</label>
                <input
                  id="headline"
                  type="text"
                  value={form.article_title}
                  onChange={(event) => update('article_title', event.target.value)}
                  placeholder="Original headline"
                  className="input"
                  maxLength={500}
                />
              </div>
              <div>
                <label className="label" htmlFor="url">Article URL (optional)</label>
                <input
                  id="url"
                  type="url"
                  value={form.source_url}
                  onChange={(event) => update('source_url', event.target.value)}
                  placeholder="https://publisher.com/story"
                  className="input"
                  maxLength={1000}
                />
              </div>
            </div>

            <div>
              <label className="label" htmlFor="excerpt">Supporting paragraph (optional)</label>
              <textarea
                id="excerpt"
                rows={3}
                value={form.content}
                onChange={(event) => update('content', event.target.value)}
                placeholder="Paste the paragraph that contains the claim for a more precise analysis…"
                className="input resize-y"
                maxLength={8000}
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldQuestion className="h-4 w-4" />}
                {busy ? 'Assessing evidence…' : 'Run assessment'}
              </button>
              <span className="text-[11px] text-ink-400">
                Usually takes 2–10 seconds while providers respond.
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-ink-100 pt-3 text-[11px] text-ink-500 dark:border-ink-800">
              <span>Examples:</span>
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  type="button"
                  onClick={() => update('claim', example.claim)}
                  className="rounded-full border border-ink-200 px-2.5 py-1 hover:border-ink-400 dark:border-ink-700 dark:hover:border-ink-500"
                >
                  {example.label}
                </button>
              ))}
            </div>
          </form>

          {busy && (
            <div className="card flex items-center gap-3 p-5 text-sm text-ink-600 dark:text-ink-300">
              <Loader2 className="h-5 w-5 animate-spin text-signal-500" />
              <div>
                <p className="font-medium">Retrieving independent coverage…</p>
                <p className="mt-0.5 text-xs text-ink-400">
                  Searching providers, scoring claim coverage and weighing correcting language.
                </p>
              </div>
            </div>
          )}

          {error && (
            <NoteBanner tone="warning">
              {error} If providers are down, try again shortly — no result is invented.
            </NoteBanner>
          )}

          <div ref={resultRef}>
            {result && <ResultPanel result={result} onReset={() => { setResult(null); setError(''); }} />}
          </div>

          {user && (history.data?.length || 0) > 0 && (
            <section className="card overflow-hidden">
              <div className="flex items-center gap-2 border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
                <History className="h-4 w-4 text-ink-400" aria-hidden />
                <h2 className="text-sm font-bold uppercase tracking-widest text-ink-500">Your recent checks</h2>
              </div>
              <ul className="divide-y divide-ink-100 dark:divide-ink-800">
                {history.data.map((entry) => {
                  const style = VERDICT_STYLES[entry.verdict] || VERDICT_STYLES.insufficient;
                  return (
                    <li key={entry.id}>
                      <button
                        type="button"
                        onClick={() => loadHistory(entry)}
                        className="flex w-full items-start justify-between gap-3 px-5 py-3 text-left hover:bg-ink-50 dark:hover:bg-ink-800/60"
                      >
                        <div>
                          <p className="line-clamp-1 text-sm">{entry.claim}</p>
                          <p className="mt-0.5 text-[11px] text-ink-400">
                            {timeAgo(entry.created_at)} · {percent(entry.confidence)} confidence
                          </p>
                        </div>
                        <span className={cx('shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize', style.tone)}>
                          {entry.verdict}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
        </div>

        <aside className="space-y-5">
          <section className="card p-5">
            <h2 className="flex items-center gap-2 text-sm font-bold">
              <Scale className="h-4 w-4 text-accent-600" aria-hidden /> How this works
            </h2>
            <ol className="mt-3 space-y-3 text-xs leading-5 text-ink-600 dark:text-ink-400">
              <li><span className="font-semibold text-ink-900 dark:text-ink-100">1. Extract the claim.</span> Headline, URL metadata and your paragraph are combined into a concise assertion.</li>
              <li><span className="font-semibold text-ink-900 dark:text-ink-100">2. Retrieve evidence.</span> Broad and narrow searches run against independent publishers and fact-check coverage.</li>
              <li><span className="font-semibold text-ink-900 dark:text-ink-100">3. Score stance.</span> Each item is checked for claim-term coverage plus explicit confirming or correcting language.</li>
              <li><span className="font-semibold text-ink-900 dark:text-ink-100">4. Be conservative.</span> Two or more consistent items from established publishers are needed before a claim is labelled supported or contradicted.</li>
            </ol>
          </section>

          <section className="rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
            <h2 className="text-sm font-bold">What this is not</h2>
            <ul className="mt-3 space-y-2 text-xs leading-5 text-ink-500 dark:text-ink-400">
              <li>Not a fake-news detector and not a trained truth classifier.</li>
              <li>Not proof: repeated coverage is not independent verification.</li>
              <li>Only evidence attributed to an established publisher can move the verdict; that allowlist is a heuristic.</li>
              <li>Not exhaustive: providers and search limits shape what can be found.</li>
              <li>Not a replacement for reading the cited sources or professional fact-checkers.</li>
            </ul>
          </section>

          <NoteBanner tone="warning">
            Automated keyword scoring can misread negation, sarcasm and context. Treat the
            label as a starting point, not a conclusion.
          </NoteBanner>
        </aside>
      </div>
    </div>
  );
}
