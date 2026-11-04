import { AlertTriangle, FileText, Sparkles, Wand2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { aiApi, apiErrorMessage } from '../lib/api';
import { cx } from '../lib/format';
import { SkeletonLines } from './Skeletons';

export default function SummaryPanel({ articleId, onClose }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setResult(null);
    setError('');
  }, [articleId]);

  async function run(length) {
    setLoading(length);
    setError('');
    try {
      const { data } = await aiApi.summarize({ article_id: articleId, length });
      setResult(data);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading('');
    }
  }

  return (
    <section className="card overflow-hidden" aria-label="AI article summary">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 bg-gradient-to-r from-ink-50 to-white px-5 py-3.5 dark:border-ink-800 dark:from-ink-900 dark:to-ink-900">
        <h2 className="flex items-center gap-2 text-sm font-bold">
          <Sparkles className="h-4 w-4 text-signal-500" aria-hidden />
          Summarize this article
        </h2>
        {onClose && (
          <button type="button" onClick={onClose} className="text-xs text-ink-500 hover:text-ink-900 dark:hover:text-white">
            Close
          </button>
        )}
      </div>

      <div className="p-5">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={() => run('short')}
            disabled={Boolean(loading)}
          >
            <Wand2 className={cx('h-3.5 w-3.5', loading === 'short' && 'animate-pulse')} />
            Short summary
          </button>
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => run('detailed')}
            disabled={Boolean(loading)}
          >
            <FileText className={cx('h-3.5 w-3.5', loading === 'detailed' && 'animate-pulse')} />
            Detailed summary
          </button>
        </div>

        <p className="mt-3 text-[11px] leading-5 text-ink-500 dark:text-ink-400">
          NewsHub uses publisher feed text and, where permitted, attempts to extract
          the public article page. It does not bypass paywalls or access restrictions,
          and the panel identifies how much source text was available.
        </p>

        {loading && (
          <div className="mt-4">
            <SkeletonLines count={4} />
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            {error}
          </div>
        )}

        {result && !loading && (
          <div className="mt-4 animate-fade-in">
            <div className="rounded-xl border border-ink-200 bg-ink-50/60 p-4 dark:border-ink-700 dark:bg-ink-800/40">
              <p className="text-sm leading-7 text-ink-800 dark:text-ink-100">{result.summary}</p>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-500 dark:text-ink-400">
              <span
                className={cx(
                  'rounded-full border px-2 py-0.5 font-semibold',
                  result.ai_generated
                    ? 'border-signal-500/30 bg-signal-500/10 text-signal-600 dark:text-teal-300'
                    : 'border-ink-200 bg-white dark:border-ink-700 dark:bg-ink-900'
                )}
              >
                {result.ai_generated ? 'AI model summary' : 'Local extractive summary'}
              </span>
              <span>{result.word_count} words</span>
              <span>·</span>
              <span>Based on: {(result.based_on || []).join(', ')}</span>
            </div>
            {result.content_status && (
              <p className="mt-2 text-[11px] text-ink-500 dark:text-ink-400">
                Source content: <strong>{({ full: 'Full article text', partial: 'Partial article text', headline_only: 'Headline / description only' })[result.content_status] || result.content_status}</strong>
                {Number.isFinite(result.extracted_word_count) ? ` · ${result.extracted_word_count} source words` : ''}
              </p>
            )}
            {result.warning && (
              <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-5 text-amber-700 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                {result.warning}
              </p>
            )}
            <p className="mt-2 text-[10px] leading-4 text-ink-400 dark:text-ink-500">
              {result.disclaimer}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
