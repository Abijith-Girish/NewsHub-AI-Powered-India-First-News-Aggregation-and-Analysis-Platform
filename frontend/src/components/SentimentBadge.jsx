import { Frown, Meh, Smile } from 'lucide-react';

import { SENTIMENT_STYLES, cx } from '../lib/format';

const ICONS = { positive: Smile, negative: Frown, neutral: Meh };

export default function SentimentBadge({ label, score, showScore = false, className = '' }) {
  if (!label) return null;
  const Icon = ICONS[label] || Meh;
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize',
        SENTIMENT_STYLES[label] || SENTIMENT_STYLES.neutral,
        className
      )}
      title="Sentiment describes the tone of the wording, not accuracy."
    >
      <Icon className="h-3 w-3" aria-hidden />
      {label}
      {showScore && score !== null && score !== undefined && (
        <span className="opacity-60">({Number(score).toFixed(2)})</span>
      )}
    </span>
  );
}
