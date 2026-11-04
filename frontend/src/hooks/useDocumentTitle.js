import { useEffect } from 'react';

export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · NewsHub` : 'NewsHub — Intelligent news, one place';
  }, [title]);
}
