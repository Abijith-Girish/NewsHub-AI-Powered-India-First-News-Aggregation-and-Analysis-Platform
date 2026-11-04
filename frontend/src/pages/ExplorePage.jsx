import { Compass, Info, SearchX, SlidersHorizontal } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import ArticleCard from '../components/ArticleCard';
import FilterBar from '../components/FilterBar';
import Pagination from '../components/Pagination';
import SearchBar from '../components/SearchBar';
import { SkeletonGrid } from '../components/Skeletons';
import { EmptyState, ErrorState, NoteBanner } from '../components/States';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { newsApi } from '../lib/api';

const SUGGESTIONS = [
  'Artificial intelligence',
  'Indian economy',
  'Climate policy',
  'Cybersecurity',
  'Space exploration',
  'Elections',
];

function indiaLocalDate() {
  const parts = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function cleanParams(values) {
  const next = {};
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== 'all') {
      next[key] = String(value);
    }
  });
  return next;
}

export default function ExplorePage() {
  const [params, setParams] = useSearchParams();
  const query = params.get('q') || '';
  const page = Number(params.get('page') || 1);
  const advanced = useMemo(() => ({
    exact: params.get('exact') || '',
    exclude: params.get('exclude') || '',
    author: params.get('author') || '',
    from_date: params.get('from_date') || '',
    to_date: params.get('to_date') || '',
    has_image: params.get('has_image') || 'all',
  }), [params]);
  const [advancedDraft, setAdvancedDraft] = useState(advanced);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [advancedError, setAdvancedError] = useState('');
  const indiaToday = indiaLocalDate();
  const filters = useMemo(
    () => ({
      category: params.get('category') || 'all',
      source: params.get('source') || 'all',
      date: params.get('date') || 'all',
      sort: params.get('sort') || (query ? 'relevance' : 'latest'),
    }),
    [params, query]
  );

  useDocumentTitle(query ? `Search: ${query}` : 'Explore news');

  const [searchTerm, setSearchTerm] = useState(query);
  useEffect(() => setSearchTerm(query), [query]);
  useEffect(() => setAdvancedDraft(advanced), [advanced]);

  const categories = useFetch(() => newsApi.categories().then((res) => res.data.results), []);
  const sources = useFetch(
    () =>
      newsApi.sources().then((res) =>
        (res.data.stored_sources || []).map((item) => item.source)
      ),
    []
  );

  const results = useFetch(
    () => {
      const request = {
        page,
        page_size: 20,
        category: filters.category,
        source: filters.source,
        date: filters.date,
        sort: filters.sort,
        ...advanced,
      };
      return query
        ? newsApi.search({ ...request, q: query }).then((res) => res.data)
        : newsApi.list(request).then((res) => res.data);
    },
    [query, page, filters.category, filters.source, filters.date, filters.sort, advanced.exact, advanced.exclude, advanced.author, advanced.from_date, advanced.to_date, advanced.has_image]
  );

  const apply = useCallback(
    (next) => setParams(cleanParams(next)),
    [setParams]
  );

  function submitSearch(value) {
    apply({ q: value, category: filters.category, source: filters.source, date: filters.date, sort: filters.sort, ...advanced });
  }

  function submitAdvanced(event) {
    event.preventDefault();
    setAdvancedError('');
    const { from_date: fromDate, to_date: toDate } = advancedDraft;
    if (fromDate && fromDate > indiaToday) {
      setAdvancedError('From date cannot be later than today (India time).');
      return;
    }
    if (toDate && toDate > indiaToday) {
      setAdvancedError('To date cannot be later than today (India time).');
      return;
    }
    if (fromDate && toDate && fromDate > toDate) {
      setAdvancedError('From date must be on or before To date.');
      return;
    }
    apply({ q: query, category: filters.category, source: filters.source, date: filters.date, sort: filters.sort, ...advancedDraft });
  }

  const data = results.data;
  const articles = data?.results || [];
  const meta = data?.meta;

  return (
    <div className="container-page py-8">
      <header className="mx-auto max-w-3xl text-center">
        <p className="eyebrow">Explore</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">
          Search any topic across publishers
        </h1>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-ink-500 dark:text-ink-400">
          Search Indian and international publishers together. Cross-publisher reporting is retained for comparison and ranked by relevance or recency.
        </p>
      </header>

      <div className="mx-auto mt-6 max-w-3xl">
        <SearchBar initialValue={searchTerm} onSubmit={submitSearch} autoFocus={!query} />
        <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-xs text-ink-500">
          <span className="inline-flex items-center gap-1">
            <Compass className="h-3.5 w-3.5" aria-hidden /> Try:
          </span>
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => submitSearch(suggestion)}
              className="rounded-full border border-ink-200 px-2.5 py-1 text-[11px] hover:border-ink-400 hover:text-ink-800 dark:border-ink-700 dark:hover:border-ink-500 dark:hover:text-white"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8">
        <FilterBar
          filters={filters}
          sources={sources.data || []}
          categories={categories.data || []}
          onChange={(next) =>
            apply({
              q: query,
              category: next.category,
              source: next.source,
              date: next.date,
              sort: next.sort,
              ...advanced,
            })
          }
          onReset={() => { setAdvancedDraft({ exact: '', exclude: '', author: '', from_date: '', to_date: '', has_image: 'all' }); setAdvancedError(''); apply({ q: query, sort: query ? 'relevance' : 'latest' }); }}
        />
      </div>

      <div className="mt-3 rounded-xl border border-ink-200 bg-white dark:border-ink-800 dark:bg-ink-900">
        <button type="button" onClick={() => setAdvancedOpen((value) => !value)} className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-semibold">
          <SlidersHorizontal className="h-4 w-4" /> Advanced search {advancedOpen ? '−' : '+'}
        </button>
        {advancedOpen && (
          <form onSubmit={submitAdvanced} className="grid gap-3 border-t border-ink-100 p-4 dark:border-ink-800 sm:grid-cols-2 lg:grid-cols-3">
            <label className="block"><span className="label">Exact phrase</span><input className="input" value={advancedDraft.exact} onChange={(event) => setAdvancedDraft((old) => ({ ...old, exact: event.target.value }))} placeholder="Phrase that must appear" /></label>
            <label className="block"><span className="label">Exclude words</span><input className="input" value={advancedDraft.exclude} onChange={(event) => setAdvancedDraft((old) => ({ ...old, exclude: event.target.value }))} placeholder="e.g. rumours speculation" /></label>
            <label className="block"><span className="label">Author</span><input className="input" value={advancedDraft.author} onChange={(event) => setAdvancedDraft((old) => ({ ...old, author: event.target.value }))} placeholder="Author name" /></label>
            <label className="block"><span className="label">From date</span><input type="date" max={indiaToday} className="input" value={advancedDraft.from_date} onChange={(event) => setAdvancedDraft((old) => ({ ...old, from_date: event.target.value }))} /></label>
            <label className="block"><span className="label">To date</span><input type="date" min={advancedDraft.from_date || undefined} max={indiaToday} className="input" value={advancedDraft.to_date} onChange={(event) => setAdvancedDraft((old) => ({ ...old, to_date: event.target.value }))} /></label>
            <label className="block"><span className="label">Image availability</span><select className="select" value={advancedDraft.has_image} onChange={(event) => setAdvancedDraft((old) => ({ ...old, has_image: event.target.value }))}><option value="all">All articles</option><option value="1">Has image</option><option value="0">No image</option></select></label>
            {advancedError && <p role="alert" className="text-sm text-rose-600 sm:col-span-2 lg:col-span-3">{advancedError}</p>}
            <div className="sm:col-span-2 lg:col-span-3"><button type="submit" className="btn-primary btn-sm">Apply advanced filters</button></div>
          </form>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">
            {query ? (
              <>
                Results for <span className="text-accent-700 dark:text-accent-400">“{query}”</span>
              </>
            ) : (
              'All stored news'
            )}
          </h2>
          <p className="meta mt-1">
            {results.loading
              ? 'Searching providers and stored articles…'
              : `${data?.count ?? 0} matching article${data?.count === 1 ? '' : 's'} (same-publisher repeats are filtered)`}
          </p>
        </div>
        {meta?.live_search && (
          <span className="rounded-full border border-ink-200 px-2.5 py-1 text-[11px] text-ink-500 dark:border-ink-700 dark:text-ink-400">
            Live providers: {meta.live_search.providers_succeeded || 0}/
            {meta.live_search.providers_attempted || 0}
          </span>
        )}
      </div>

      {meta?.live_search?.errors?.length > 0 && (
        <div className="mt-4">
          <NoteBanner tone="warning">
            Some providers were unavailable ({meta.live_search.errors.join('; ')}). Results
            from stored articles and reachable sources are shown below.
          </NoteBanner>
        </div>
      )}

      {meta?.count_note && (
        <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-5 text-ink-400 dark:text-ink-500">
          <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
          {meta.count_note}
        </p>
      )}

      <div className="mt-5">
        {results.loading && <SkeletonGrid count={6} />}

        {results.error && <ErrorState message={results.error} onRetry={results.reload} />}

        {!results.loading && !results.error && !articles.length && (
          <EmptyState
            icon={SearchX}
            title={query ? 'No articles matched that search' : 'Nothing stored yet'}
            message={
              query
                ? 'Providers may not have coverage for this wording yet. Try a broader topic, remove filters, or check the spelling.'
                : 'The feed is empty. Refresh the page once providers respond.'
            }
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <button
                  type="button"
                  className="btn-primary btn-sm"
                  onClick={() => apply({ q: query, sort: filters.sort })}
                >
                  Clear filters
                </button>
                <Link to="/" className="btn-secondary btn-sm">
                  Back to home
                </Link>
              </div>
            }
          />
        )}

        {articles.length > 0 && (
          <>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {articles.map((article, index) => (
                <ArticleCard key={article.id} article={article} priority={index < 3} />
              ))}
            </div>
            <Pagination
              page={data.page}
              pages={data.pages}
              onChange={(nextPage) =>
                apply({
                  q: query,
                  category: filters.category,
                  source: filters.source,
                  date: filters.date,
                  sort: filters.sort,
                  page: nextPage,
                  ...advanced,
                })
              }
            />
          </>
        )}
      </div>
    </div>
  );
}
