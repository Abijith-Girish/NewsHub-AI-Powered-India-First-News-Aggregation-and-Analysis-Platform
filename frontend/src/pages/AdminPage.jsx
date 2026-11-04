import {
  BarChart3,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Gauge,
  Loader2,
  Newspaper,
  Pencil,
  Plus,
  RefreshCw,
  Tags,
  Trash2,
  Users,
  X,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { SkeletonLines } from '../components/Skeletons';
import { ErrorState, NoteBanner } from '../components/States';
import { adminApi, aiApi, apiErrorMessage } from '../lib/api';
import { cx, formatDate, formatDateTime, percent, timeAgo } from '../lib/format';
import { toast } from '../lib/toast';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useFetch } from '../hooks/useFetch';

const TABS = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'articles', label: 'Articles', icon: Newspaper },
  { id: 'review', label: 'ML review', icon: Gauge },
  { id: 'categories', label: 'Categories', icon: Tags },
  { id: 'users', label: 'Users', icon: Users },
];

const STATUS_STYLES = {
  published: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900',
  draft: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900',
  archived: 'bg-ink-100 text-ink-600 border-ink-200 dark:bg-ink-800 dark:text-ink-300 dark:border-ink-700',
};

function StatCard({ label, value, hint }) {
  return (
    <div className="card p-4">
      <p className="text-2xl font-bold leading-tight">{value}</p>
      <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{label}</p>
      {hint && <p className="mt-1 text-[11px] text-ink-400">{hint}</p>}
    </div>
  );
}

function SectionCard({ title, action, children }) {
  return (
    <section className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
        <h2 className="text-sm font-bold uppercase tracking-widest text-ink-500">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ editor */

function toInputDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
}

function ArticleEditor({ initial, categories, onClose, onSaved }) {
  const isEdit = Boolean(initial?.id);
  const [form, setForm] = useState({
    title: initial?.title || '',
    description: initial?.description || '',
    content: initial?.content || '',
    image_url: initial?.image_url || '',
    source_name: initial?.source_name || '',
    source_url: initial?.source_url || '',
    author: initial?.author || '',
    published_at: toInputDate(initial?.published_at || new Date().toISOString()),
    // Admin endpoints serialize the category as a primary key.
    category: initial?.category || '',
    status: initial?.status || 'published',
    is_breaking: Boolean(initial?.is_breaking),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const payload = {
      title: form.title.trim(),
      description: form.description.trim(),
      content: form.content,
      image_url: form.image_url.trim(),
      source_name: form.source_name.trim(),
      source_url: form.source_url.trim(),
      author: form.author.trim(),
      category: form.category ? Number(form.category) : null,
      status: form.status,
      is_breaking: form.is_breaking,
    };
    if (form.published_at) payload.published_at = new Date(form.published_at).toISOString();
    try {
      if (isEdit) {
        await adminApi.updateArticle(initial.id, payload);
        toast('Article updated', 'success');
      } else {
        await adminApi.createArticle(payload);
        toast('Article created', 'success');
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-950/50 p-4 backdrop-blur-sm">
      <div className="my-6 w-full max-w-3xl rounded-2xl border border-ink-200 bg-white shadow-lift dark:border-ink-700 dark:bg-ink-900">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4 dark:border-ink-800">
          <h2 className="text-lg font-bold">{isEdit ? 'Edit article' : 'New article'}</h2>
          <button type="button" onClick={onClose} className="rounded-full p-1.5 hover:bg-ink-100 dark:hover:bg-ink-800" aria-label="Close editor">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={submit} className="space-y-4 p-5">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200">
              {error}
            </div>
          )}
          <div>
            <label className="label" htmlFor="a-title">Title</label>
            <input id="a-title" className="input" required minLength={5} value={form.title} onChange={(event) => update('title', event.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="a-desc">Description</label>
            <textarea id="a-desc" className="input resize-y" rows={2} value={form.description} onChange={(event) => update('description', event.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="a-content">Content (optional, only if you have rights)</label>
            <textarea id="a-content" className="input resize-y" rows={5} value={form.content} onChange={(event) => update('content', event.target.value)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="a-source">Source name</label>
              <input id="a-source" className="input" value={form.source_name} onChange={(event) => update('source_name', event.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="a-url">Source URL</label>
              <input id="a-url" className="input" type="url" required value={form.source_url} onChange={(event) => update('source_url', event.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="a-author">Author</label>
              <input id="a-author" className="input" value={form.author} onChange={(event) => update('author', event.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="a-image">Image URL</label>
              <input id="a-image" className="input" type="url" value={form.image_url} onChange={(event) => update('image_url', event.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="a-cat">Category</label>
              <select id="a-cat" className="select" value={form.category} onChange={(event) => update('category', event.target.value)}>
                <option value="">No category</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="a-status">Status</label>
              <select id="a-status" className="select" value={form.status} onChange={(event) => update('status', event.target.value)}>
                <option value="published">Published</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div>
              <label className="label" htmlFor="a-date">Publication date</label>
              <input id="a-date" type="datetime-local" className="input" value={form.published_at} onChange={(event) => update('published_at', event.target.value)} />
            </div>
            <label className="flex items-end gap-2 pb-2.5 text-sm">
              <input type="checkbox" checked={form.is_breaking} onChange={(event) => update('is_breaking', event.target.checked)} className="h-4 w-4 rounded border-ink-300 text-accent-600" />
              Flag as breaking (use sparingly)
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t border-ink-100 pt-4 dark:border-ink-800">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              {isEdit ? 'Save changes' : 'Create article'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- overview */

function OverviewTab({ dashboard, metrics, onRefresh }) {
  const [ingesting, setIngesting] = useState(false);

  async function ingest() {
    setIngesting(true);
    try {
      const { data } = await adminApi.ingest('all');
      toast(
        `Providers: ${data.providers_succeeded}/${data.providers_attempted} · +${data.created} new, ${data.updated} updated`,
        'success'
      );
      onRefresh();
    } catch (error) {
      toast(apiErrorMessage(error), 'error');
    } finally {
      setIngesting(false);
    }
  }

  if (dashboard.loading) return <div className="card p-8"><SkeletonLines count={10} /></div>;
  if (dashboard.error) return <ErrorState message={dashboard.error} onRetry={dashboard.reload} />;
  const data = dashboard.data;
  if (!data) return null;

  const model = data.model || {};
  const perClass = metrics.data?.metrics?.per_class || {};

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Published" value={data.articles.published} hint={`${data.articles.last_24h} in the last 24h`} />
        <StatCard label="All articles" value={data.articles.total} hint={`${data.articles.drafts} drafts · ${data.articles.archived} archived`} />
        <StatCard label="Registered users" value={data.users.total} hint={`${data.users.new_7d} joined this week`} />
        <StatCard label="Saved articles" value={data.engagement.saved_articles} hint={`${data.engagement.fact_checks} fact checks`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <SectionCard
          title="Category classifier"
          action={
            <span className={cx('rounded-full border px-2 py-0.5 text-[10px] font-semibold', model.available ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300' : 'border-amber-200 bg-amber-50 text-amber-700')}>
              {model.available ? 'Model ready' : 'Not trained'}
            </span>
          }
        >
          <div className="grid gap-4 p-5 sm:grid-cols-3">
            <div>
              <p className="text-2xl font-bold">{percent(model.accuracy)}</p>
              <p className="text-[11px] uppercase tracking-wider text-ink-400">Accuracy</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{percent(model.macro_f1)}</p>
              <p className="text-[11px] uppercase tracking-wider text-ink-400">Macro F1</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{model.dataset_rows ?? '—'}</p>
              <p className="text-[11px] uppercase tracking-wider text-ink-400">Training rows</p>
            </div>
          </div>
          <div className="border-t border-ink-100 px-5 py-3 text-[11px] text-ink-400 dark:border-ink-800">
            TF-IDF word + char n-grams · logistic regression · trained{' '}
            {model.trained_at ? timeAgo(model.trained_at) : '—'}. Evaluated on a held-out split of
            a curated seed corpus, not a public benchmark.
          </div>
          {Object.keys(perClass).length > 0 && (
            <div className="border-t border-ink-100 dark:border-ink-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-ink-50 text-[10px] uppercase tracking-wider text-ink-400 dark:bg-ink-800/50">
                  <tr>
                    <th className="px-5 py-2 font-semibold">Class</th>
                    <th className="px-2 py-2 font-semibold">Precision</th>
                    <th className="px-2 py-2 font-semibold">Recall</th>
                    <th className="px-5 py-2 font-semibold">F1</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                  {Object.entries(perClass).map(([label, values]) => (
                    <tr key={label}>
                      <td className="px-5 py-1.5 capitalize">{label}</td>
                      <td className="px-2 py-1.5">{percent(values.precision)}</td>
                      <td className="px-2 py-1.5">{percent(values.recall)}</td>
                      <td className="px-5 py-1.5">{percent(values.f1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="border-t border-ink-100 px-5 py-2.5 text-[10px] text-ink-400 dark:border-ink-800">
            Retrain: <code className="rounded bg-ink-100 px-1 py-0.5 dark:bg-ink-800">python manage.py train_classifier</code>
          </div>
        </SectionCard>

        <div className="space-y-5">
          <SectionCard
            title="Provider status"
            action={
              <button type="button" onClick={ingest} disabled={ingesting} className="btn-secondary btn-sm">
                {ingesting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                Refresh feeds
              </button>
            }
          >
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-ink-50 text-[10px] uppercase tracking-wider text-ink-400 dark:bg-ink-800">
                  <tr>
                    <th className="px-5 py-2">Feed</th>
                    <th className="px-2 py-2">Sections</th>
                    <th className="px-5 py-2 text-right">Feeds</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                  {data.providers.map((provider) => (
                    <tr key={provider.name}>
                      <td className="px-5 py-1.5">{provider.name}</td>
                      <td className="px-2 py-1.5 text-ink-400">{provider.categories.join(', ')}</td>
                      <td className="px-5 py-1.5 text-right">{provider.feed_keys.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-ink-100 px-5 py-2.5 text-[10px] text-ink-400 dark:border-ink-800">
              Last refresh: {data.last_feeds_refresh ? timeAgo(data.last_feeds_refresh) : 'not yet this session'}
            </p>
          </SectionCard>

          <SectionCard title="Integrations">
            <div className="grid gap-2 p-5 sm:grid-cols-2">
              {[
                ['Live RSS fetch', data.config.live_fetch_enabled],
                ['LLM summaries (optional)', data.config.llm_configured],
                ['NewsAPI (optional)', data.config.newsapi_configured],
                ['GNews (optional)', data.config.gnews_configured],
              ].map(([label, enabled]) => (
                <p key={label} className="flex items-center gap-2 text-xs">
                  <span className={cx('h-2 w-2 rounded-full', enabled ? 'bg-emerald-500' : 'bg-ink-300 dark:bg-ink-600')} />
                  {label}
                  <span className="ml-auto text-[10px] uppercase tracking-wider text-ink-400">
                    {enabled ? 'on' : 'off'}
                  </span>
                </p>
              ))}
            </div>
            <p className="border-t border-ink-100 px-5 py-2.5 text-[10px] leading-4 text-ink-400 dark:border-ink-800">
              Keys are read from backend environment variables and never sent to the browser.
              Without an LLM key the app uses local extractive summaries.
            </p>
          </SectionCard>
        </div>
      </div>

      <SectionCard
        title="Recent articles"
        action={<Link to="/admin?tab=articles" className="text-xs font-medium text-ink-500 hover:text-ink-900 dark:hover:text-white">Manage all</Link>}
      >
        <ul className="divide-y divide-ink-100 dark:divide-ink-800">
          {data.recent_articles.map((article) => (
            <li key={article.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5 text-sm">
              <div className="min-w-0">
                <p className="line-clamp-1 font-medium">{article.title}</p>
                <p className="text-[11px] text-ink-400">
                  {article.source_name || 'NewsHub editorial'} · {formatDate(article.published_at)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={cx('rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize', STATUS_STYLES[article.status])}>
                  {article.status}
                </span>
                <Link to={`/article/${article.id}`} className="text-[11px] text-ink-400 hover:text-ink-900 dark:hover:text-white">
                  View
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </SectionCard>
    </div>
  );
}

/* ----------------------------------------------------------------- articles */

function ArticlesTab({ categories, onChanged }) {
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState(null);

  const articles = useFetch(
    () =>
      adminApi
        .articles({ q: query || undefined, status: status || undefined, page, page_size: 10 })
        .then((res) => res.data),
    [query, status, page]
  );

  async function remove(article) {
    if (!window.confirm(`Delete “${article.title}”? This removes it from the database.`)) return;
    try {
      await adminApi.deleteArticle(article.id);
      toast('Article deleted', 'success');
      articles.reload();
      onChanged();
    } catch (error) {
      toast(apiErrorMessage(error), 'error');
    }
  }

  function refresh() {
    articles.reload();
    onChanged();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setQuery(searchInput.trim());
          }}
          className="flex flex-1 gap-2"
        >
          <input
            className="input max-w-sm"
            placeholder="Search title, source or description…"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            aria-label="Search articles"
          />
          <button type="submit" className="btn-secondary btn-sm">Search</button>
        </form>
        <select
          className="select w-auto"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </select>
        <button type="button" className="btn-primary btn-sm" onClick={() => setEditor({})}>
          <Plus className="h-3.5 w-3.5" /> New article
        </button>
      </div>

      {articles.loading && <div className="card p-6"><SkeletonLines count={8} /></div>}
      {articles.error && <ErrorState message={articles.error} onRetry={articles.reload} />}

      {articles.data && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-ink-50 text-[10px] uppercase tracking-wider text-ink-400 dark:bg-ink-800/60">
                <tr>
                  <th className="px-4 py-2.5">Title</th>
                  <th className="px-4 py-2.5">Source</th>
                  <th className="px-4 py-2.5">Category</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Published</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
                {articles.data.results.map((article) => (
                  <tr key={article.id} className="hover:bg-ink-50/60 dark:hover:bg-ink-800/30">
                    <td className="max-w-xs px-4 py-2.5">
                      <p className="line-clamp-2 font-medium">{article.title}</p>
                      <p className="text-[10px] text-ink-400">#{article.id}</p>
                    </td>
                    <td className="px-4 py-2.5 text-xs">{article.source_name || '—'}</td>
                    <td className="px-4 py-2.5 text-xs">
                      {categories.find((category) => category.id === article.category)?.name || '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cx('rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize', STATUS_STYLES[article.status])}>
                        {article.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-ink-400">{formatDate(article.published_at)}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <a
                          href={article.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-800 dark:hover:bg-ink-800 dark:hover:text-white"
                          aria-label="Open source URL"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                        <button type="button" onClick={() => setEditor(article)} className="rounded p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-800 dark:hover:bg-ink-800 dark:hover:text-white" aria-label="Edit article">
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button type="button" onClick={() => remove(article)} className="rounded p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40" aria-label="Delete article">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!articles.data.results.length && (
            <p className="px-5 py-10 text-center text-sm text-ink-500">No articles match those filters.</p>
          )}
          <div className="flex items-center justify-between border-t border-ink-100 px-4 py-2.5 text-xs text-ink-500 dark:border-ink-800">
            <span>{articles.data.count} articles</span>
            <div className="flex items-center gap-1">
              <button type="button" className="rounded p-1.5 hover:bg-ink-100 disabled:opacity-30 dark:hover:bg-ink-800" disabled={!articles.data.previous} onClick={() => setPage((value) => Math.max(1, value - 1))} aria-label="Previous page">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span>Page {articles.data.page} of {articles.data.pages}</span>
              <button type="button" className="rounded p-1.5 hover:bg-ink-100 disabled:opacity-30 dark:hover:bg-ink-800" disabled={!articles.data.next} onClick={() => setPage((value) => value + 1)} aria-label="Next page">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {editor && (
        <ArticleEditor
          initial={editor}
          categories={categories}
          onClose={() => setEditor(null)}
          onSaved={refresh}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- review */

function ReviewTab({ categories, onChanged }) {
  const queue = useFetch(() => adminApi.reviewQueue().then((res) => res.data), []);
  const [busyId, setBusyId] = useState(null);
  const [overrides, setOverrides] = useState({});

  async function apply(article, payload) {
    setBusyId(article.id);
    try {
      await adminApi.setCategory(article.id, payload);
      toast('Category updated', 'success');
      queue.reload();
      onChanged();
    } catch (error) {
      toast(apiErrorMessage(error), 'error');
    } finally {
      setBusyId(null);
    }
  }

  if (queue.loading) return <div className="card p-6"><SkeletonLines count={8} /></div>;
  if (queue.error) return <ErrorState message={queue.error} onRetry={queue.reload} />;

  return (
    <div className="space-y-4">
      <NoteBanner>
        This queue lists articles whose displayed category came from the model or keyword
        rules and still needs confirmation. Provider-assigned sections are treated as
        authoritative and are not listed. Accepting a suggestion records it as an ML choice.
      </NoteBanner>

      {!queue.data?.results?.length ? (
        <div className="card p-10 text-center text-sm text-ink-500">
          <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" />
          <p className="mt-3 font-medium">Nothing to review</p>
          <p className="mt-1 text-xs">Every model-assigned article has been confirmed or is above the confidence threshold.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {queue.data.results.map((article) => (
            <li key={article.id} className="card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <Link to={`/article/${article.id}`} className="line-clamp-2 font-display text-base font-semibold hover:text-accent-700 dark:hover:text-accent-300">
                    {article.title}
                  </Link>
                  <p className="mt-1 text-[11px] text-ink-400">
                    {article.source || 'Unknown source'} · {formatDateTime(article.published_at)}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="rounded-full border border-ink-200 px-2 py-0.5 dark:border-ink-700">
                      Shown: {article.category?.name || 'none'}
                    </span>
                    <span className="rounded-full border border-signal-500/30 bg-signal-500/10 px-2 py-0.5 text-signal-600 dark:text-teal-300">
                      ML: {article.ml_category?.name || 'none'} ({percent(article.ml_confidence)})
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    disabled={!article.ml_category || busyId === article.id}
                    onClick={() => apply(article, { accept_ml: true })}
                  >
                    {busyId === article.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                    Accept ML
                  </button>
                  <select
                    className="select w-auto py-1.5 text-xs"
                    value={overrides[article.id] || ''}
                    onChange={(event) => setOverrides({ ...overrides, [article.id]: event.target.value })}
                    aria-label={`Override category for ${article.title}`}
                  >
                    <option value="">Choose override…</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.slug}>{category.name}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    disabled={!overrides[article.id] || busyId === article.id}
                    onClick={() => apply(article, { category_slug: overrides[article.id] })}
                  >
                    Apply
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- categories */

function slugify(value) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-');
}

function CategoriesTab({ onChanged }) {
  const categories = useFetch(() => adminApi.categories().then((res) => res.data.results), []);
  const [form, setForm] = useState({ name: '', slug: '', description: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await adminApi.createCategory({
        name: form.name.trim(),
        slug: form.slug.trim() || slugify(form.name),
        description: form.description.trim(),
      });
      setForm({ name: '', slug: '', description: '' });
      toast('Category created', 'success');
      categories.reload();
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(category) {
    if (!window.confirm(`Delete the “${category.name}” category?`)) return;
    try {
      await adminApi.deleteCategory(category.id);
      toast('Category deleted', 'success');
      categories.reload();
      onChanged();
    } catch (err) {
      toast(apiErrorMessage(err), 'error');
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <form onSubmit={create} className="card h-fit space-y-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-ink-500">
          <Plus className="h-4 w-4" /> New category
        </h2>
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <div>
          <label className="label" htmlFor="c-name">Name</label>
          <input
            id="c-name"
            className="input"
            required
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                name: event.target.value,
                slug: current.slug || slugify(event.target.value),
              }))
            }
          />
        </div>
        <div>
          <label className="label" htmlFor="c-slug">Slug</label>
          <input
            id="c-slug"
            className="input"
            required
            value={form.slug}
            onChange={(event) => setForm({ ...form, slug: event.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="c-desc">Description</label>
          <textarea
            id="c-desc"
            rows={3}
            className="input resize-y"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </div>
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Create
        </button>
        <p className="text-[10px] leading-4 text-ink-400">
          Categories with articles cannot be deleted; move or delete those articles first.
        </p>
      </form>

      <div className="card overflow-hidden lg:col-span-2">
        <div className="border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
          <h2 className="text-sm font-bold uppercase tracking-widest text-ink-500">All categories</h2>
        </div>
        {categories.loading && <div className="p-5"><SkeletonLines count={6} /></div>}
        {categories.error && <div className="p-5"><ErrorState compact message={categories.error} onRetry={categories.reload} /></div>}
        <ul className="divide-y divide-ink-100 dark:divide-ink-800">
          {(categories.data || []).map((category) => (
            <li key={category.id} className="flex items-center justify-between gap-3 px-5 py-2.5">
              <div>
                <p className="text-sm font-medium">{category.name}</p>
                <p className="text-[11px] text-ink-400">/{category.slug} · {category.article_count} articles</p>
              </div>
              <button type="button" onClick={() => remove(category)} className="rounded p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40" aria-label={`Delete ${category.name}`}>
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------- users */

function UsersTab() {
  const users = useFetch(() => adminApi.users().then((res) => res.data), []);
  if (users.loading) return <div className="card p-6"><SkeletonLines count={8} /></div>;
  if (users.error) return <ErrorState message={users.error} onRetry={users.reload} />;

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
        <h2 className="text-sm font-bold uppercase tracking-widest text-ink-500">
          Registered users ({users.data?.count ?? 0})
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-ink-50 text-[10px] uppercase tracking-wider text-ink-400 dark:bg-ink-800/60">
            <tr>
              <th className="px-4 py-2.5">User</th>
              <th className="px-4 py-2.5">Email</th>
              <th className="px-4 py-2.5">Role</th>
              <th className="px-4 py-2.5">Joined</th>
              <th className="px-4 py-2.5 text-right">Saved</th>
              <th className="px-4 py-2.5 text-right">Fact checks</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
            {users.data?.results.map((account) => (
              <tr key={account.id}>
                <td className="px-4 py-2.5 font-medium">{account.username}</td>
                <td className="px-4 py-2.5 text-xs text-ink-500">{account.email}</td>
                <td className="px-4 py-2.5 text-xs">
                  {account.is_staff ? (
                    <span className="rounded-full bg-signal-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-600 dark:text-teal-300">Staff</span>
                  ) : (
                    'Reader'
                  )}
                </td>
                <td className="px-4 py-2.5 text-xs text-ink-400">{formatDate(account.date_joined)}</td>
                <td className="px-4 py-2.5 text-right text-xs">{account.saved_count}</td>
                <td className="px-4 py-2.5 text-right text-xs">{account.fact_check_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- page */

export default function AdminPage() {
  useDocumentTitle('Admin dashboard');
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return TABS.some((item) => item.id === requested) ? requested : 'overview';
  });
  const [reloadTick, setReloadTick] = useState(0);

  const dashboard = useFetch(
    () => adminApi.dashboard().then((res) => res.data),
    [tab, reloadTick],
    { skip: tab !== 'overview' }
  );
  const metrics = useFetch(
    () => aiApi.metrics().then((res) => res.data),
    [],
    { skip: tab !== 'overview' }
  );
  const categories = useFetch(
    () => adminApi.categories().then((res) => res.data.results),
    [reloadTick]
  );

  const categoryList = useMemo(() => categories.data || [], [categories.data]);

  function refreshAll() {
    setReloadTick((value) => value + 1);
    categories.reload();
  }

  return (
    <div className="container-page py-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-ink-200 pb-5 dark:border-ink-800">
        <div>
          <p className="eyebrow">Restricted area</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">Admin dashboard</h1>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
            Manage published content, review model predictions and monitor providers.
          </p>
        </div>
        <button type="button" onClick={refreshAll} className="btn-secondary btn-sm">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh data
        </button>
      </header>

      <div className="no-scrollbar mt-5 flex gap-1 overflow-x-auto border-b border-ink-200 dark:border-ink-800">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={cx(
              'flex shrink-0 items-center gap-1.5 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors',
              tab === item.id
                ? 'border-accent-600 text-ink-900 dark:text-white'
                : 'border-transparent text-ink-500 hover:text-ink-900 dark:hover:text-white'
            )}
            aria-current={tab === item.id ? 'page' : undefined}
          >
            <item.icon className="h-4 w-4" aria-hidden /> {item.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === 'overview' && (
          <OverviewTab dashboard={dashboard} metrics={metrics} onRefresh={refreshAll} />
        )}
        {tab === 'articles' && <ArticlesTab categories={categoryList} onChanged={refreshAll} />}
        {tab === 'review' && <ReviewTab categories={categoryList} onChanged={refreshAll} />}
        {tab === 'categories' && <CategoriesTab onChanged={refreshAll} />}
        {tab === 'users' && <UsersTab />}
      </div>

      {tab !== 'overview' && (
        <div className="mt-8">
          <NoteBanner>
            All admin endpoints require a staff account and are checked server-side. Ordinary
            users receive 403 responses even if they reach these routes directly.
          </NoteBanner>
        </div>
      )}
    </div>
  );
}
