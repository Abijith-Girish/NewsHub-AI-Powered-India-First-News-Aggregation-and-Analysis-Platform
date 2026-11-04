import { useCallback, useEffect, useRef, useState } from 'react';

import { apiErrorMessage } from '../lib/api';

/**
 * Runs `fetcher` whenever `deps` change and exposes data/loading/error.
 * Late responses from superseded requests are ignored, so filters and pages
 * never render stale results.
 */
export function useFetch(fetcher, deps = [], { skip = false, initialData = null } = {}) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const requestId = useRef(0);

  const reload = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    if (skip) {
      setLoading(false);
      return undefined;
    }
    const current = requestId.current + 1;
    requestId.current = current;
    let active = true;
    setLoading(true);
    setError('');

    Promise.resolve(fetcher())
      .then((result) => {
        if (!active || requestId.current !== current) return;
        setData(result);
      })
      .catch((err) => {
        if (!active || requestId.current !== current) return;
        setError(apiErrorMessage(err));
      })
      .finally(() => {
        if (active && requestId.current === current) setLoading(false);
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, skip]);

  return { data, loading, error, reload, setData };
}
