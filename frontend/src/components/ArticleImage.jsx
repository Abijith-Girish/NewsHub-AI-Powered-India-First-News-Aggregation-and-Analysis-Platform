import { useState } from 'react';

import { cx } from '../lib/format';

const GRADIENTS = {
  technology: 'from-sky-800 to-ink-900',
  'artificial-intelligence': 'from-indigo-800 to-ink-900',
  politics: 'from-stone-700 to-ink-900',
  business: 'from-teal-800 to-ink-900',
  sports: 'from-emerald-800 to-ink-900',
  entertainment: 'from-fuchsia-800 to-ink-900',
  health: 'from-rose-800 to-ink-900',
  education: 'from-amber-700 to-ink-900',
  science: 'from-cyan-800 to-ink-900',
  world: 'from-slate-700 to-ink-900',
};

export default function ArticleImage({ src, alt, category, className = '', priority = false }) {
  const [failed, setFailed] = useState(false);
  const gradient = GRADIENTS[category] || 'from-ink-700 to-ink-950';
  const showPlaceholder = !src || failed;

  if (showPlaceholder) {
    return (
      <div
        className={cx(
          'relative flex items-center justify-center overflow-hidden bg-gradient-to-br',
          gradient,
          className
        )}
        role="img"
        aria-label={alt || 'Article image unavailable'}
      >
        <span className="font-display text-4xl font-black uppercase tracking-tight text-white/25">
          {(category || 'news').replace(/-/g, ' ').slice(0, 14)}
        </span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt || ''}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      onError={() => setFailed(true)}
      className={cx('h-full w-full object-cover', className)}
    />
  );
}
