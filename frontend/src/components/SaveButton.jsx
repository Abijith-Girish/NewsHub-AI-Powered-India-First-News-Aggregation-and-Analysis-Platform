import { Bookmark, BookmarkCheck, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage, newsApi } from '../lib/api';
import { cx } from '../lib/format';
import { toast } from '../lib/toast';

export default function SaveButton({ article, className = '', label = false, size = 'md', onChange }) {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [saved, setSaved] = useState(Boolean(article?.saved));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSaved(Boolean(article?.saved));
  }, [article?.id, article?.saved]);

  async function toggle(event) {
    event.preventDefault();
    event.stopPropagation();
    if (!isAuthenticated) {
      navigate('/login', { state: { from: location } });
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      if (saved) {
        await newsApi.unsave(article.id);
        setSaved(false);
        onChange?.(false);
        toast('Removed from saved articles', 'info');
      } else {
        await newsApi.save(article.id);
        setSaved(true);
        onChange?.(true);
        toast('Article saved to your reading list', 'success');
      }
    } catch (error) {
      toast(apiErrorMessage(error), 'error');
    } finally {
      setBusy(false);
    }
  }

  const iconSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';
  const Icon = busy ? Loader2 : saved ? BookmarkCheck : Bookmark;

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={saved}
      aria-label={saved ? 'Remove from saved articles' : 'Save article'}
      title={saved ? 'Saved — click to remove' : 'Save for later'}
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full transition-colors',
        label
          ? saved
            ? 'btn-secondary border-ink-900 text-ink-900 dark:border-white dark:text-white'
            : 'btn-secondary'
          : 'p-2 backdrop-blur',
        !label &&
          (saved
            ? 'bg-ink-900/90 text-white hover:bg-ink-900'
            : 'bg-white/85 text-ink-700 hover:bg-white dark:bg-ink-900/85 dark:text-ink-200'),
        className
      )}
    >
      <Icon className={cx(iconSize, busy && 'animate-spin')} aria-hidden />
      {label && <span>{saved ? 'Saved' : 'Save'}</span>}
    </button>
  );
}
