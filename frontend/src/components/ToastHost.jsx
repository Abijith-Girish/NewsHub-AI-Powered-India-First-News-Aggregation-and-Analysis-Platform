import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { cx } from '../lib/format';

const ICONS = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
};

export default function ToastHost() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    function onToast(event) {
      const item = event.detail;
      setToasts((current) => [...current.slice(-2), item]);
      window.setTimeout(() => {
        setToasts((current) => current.filter((entry) => entry.id !== item.id));
      }, 4200);
    }
    window.addEventListener('newshub:toast', onToast);
    return () => window.removeEventListener('newshub:toast', onToast);
  }, []);

  if (!toasts.length) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-5 left-1/2 z-[60] flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4"
      role="status"
      aria-live="polite"
    >
      {toasts.map((item) => {
        const Icon = ICONS[item.type] || Info;
        return (
          <div
            key={item.id}
            className={cx(
              'pointer-events-auto flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm shadow-lift backdrop-blur',
              item.type === 'error'
                ? 'border-rose-300 bg-rose-50/95 text-rose-900 dark:border-rose-800 dark:bg-rose-950/95 dark:text-rose-100'
                : item.type === 'success'
                  ? 'border-emerald-300 bg-emerald-50/95 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/95 dark:text-emerald-100'
                  : 'border-ink-200 bg-white/95 text-ink-800 dark:border-ink-700 dark:bg-ink-900/95 dark:text-ink-100'
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p className="flex-1 leading-5">{item.message}</p>
            <button
              type="button"
              onClick={() => setToasts((current) => current.filter((entry) => entry.id !== item.id))}
              className="rounded p-0.5 opacity-60 hover:opacity-100"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
