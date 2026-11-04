import { AlertTriangle, Info, Loader2, RefreshCw, SearchX } from 'lucide-react';

import { cx } from '../lib/format';

export function LoadingSpinner({ label = 'Loading', className = '' }) {
  return (
    <div className={cx('flex items-center justify-center gap-2 py-12 text-sm text-ink-500', className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorState({ message, onRetry, compact = false }) {
  return (
    <div
      role="alert"
      className={cx(
        'rounded-2xl border border-rose-200 bg-rose-50/70 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200',
        compact ? 'p-4' : 'p-8'
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
        <div className="flex-1">
          <p className="text-sm font-semibold">Something went wrong</p>
          <p className="mt-1 text-sm leading-6 opacity-90">{message}</p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="btn-secondary btn-sm mt-3">
              <RefreshCw className="h-3.5 w-3.5" /> Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', message, action, icon: Icon = SearchX }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-300 px-6 py-14 text-center dark:border-ink-700">
      <Icon className="h-8 w-8 text-ink-400" aria-hidden />
      <h3 className="mt-3 text-lg font-semibold">{title}</h3>
      {message && (
        <p className="mt-1.5 max-w-sm text-sm leading-6 text-ink-500 dark:text-ink-400">
          {message}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function NoteBanner({ children, tone = 'info', className = '' }) {
  const tones = {
    info: 'border-ink-200 bg-white text-ink-600 dark:border-ink-700 dark:bg-ink-900 dark:text-ink-300',
    warning:
      'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200',
    success:
      'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200',
  };
  return (
    <div className={cx('flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-xs leading-5', tones[tone], className)}>
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}
