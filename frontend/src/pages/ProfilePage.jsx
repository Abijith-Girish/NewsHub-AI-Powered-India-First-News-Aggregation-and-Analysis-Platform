import {
  Bookmark,
  Check,
  Loader2,
  LogOut,
  Save,
  ShieldQuestion,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { SkeletonLines } from '../components/Skeletons';
import { ErrorState } from '../components/States';
import { useAuth } from '../context/AuthContext';
import { useFetch } from '../hooks/useFetch';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiErrorMessage, authApi, factCheckApi, newsApi } from '../lib/api';
import { VERDICT_STYLES, cx, formatDate, initials, percent, timeAgo } from '../lib/format';
import { toast } from '../lib/toast';

export default function ProfilePage() {
  useDocumentTitle('Profile & interests');
  const navigate = useNavigate();
  const { user, logout, refreshUser } = useAuth();

  const categories = useFetch(() => newsApi.categories().then((res) => res.data.results), []);
  const preferences = useFetch(() => authApi.preferences().then((res) => res.data), []);
  const saved = useFetch(() => newsApi.saved().then((res) => res.data), []);
  const checks = useFetch(() => factCheckApi.history().then((res) => res.data), []);

  const [selected, setSelected] = useState([]);
  const [personalize, setPersonalize] = useState(true);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [prefsError, setPrefsError] = useState('');
  const [prefsSaved, setPrefsSaved] = useState(false);

  const [account, setAccount] = useState({ first_name: '', last_name: '', email: '' });
  const [savingAccount, setSavingAccount] = useState(false);
  const [accountError, setAccountError] = useState('');

  useEffect(() => {
    if (preferences.data) {
      setSelected(preferences.data.preferred_categories || []);
      setPersonalize(Boolean(preferences.data.personalize_feed));
    }
  }, [preferences.data]);

  useEffect(() => {
    if (user) {
      setAccount({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || '',
      });
    }
  }, [user]);

  function toggleCategory(slug) {
    setPrefsSaved(false);
    setSelected((current) =>
      current.includes(slug) ? current.filter((item) => item !== slug) : [...current, slug]
    );
  }

  async function savePreferences() {
    setSavingPrefs(true);
    setPrefsError('');
    setPrefsSaved(false);
    try {
      const { data } = await authApi.updatePreferences({
        preferred_categories: selected,
        personalize_feed: personalize,
      });
      setSelected(data.preferred_categories || []);
      setPersonalize(Boolean(data.personalize_feed));
      setPrefsSaved(true);
      toast('Interests updated — your recommendations will adapt', 'success');
    } catch (error) {
      setPrefsError(apiErrorMessage(error));
      toast(apiErrorMessage(error), 'error');
    } finally {
      setSavingPrefs(false);
    }
  }

  async function saveAccount(event) {
    event.preventDefault();
    setSavingAccount(true);
    setAccountError('');
    try {
      await authApi.updateProfile(account);
      await refreshUser();
      toast('Profile details updated', 'success');
    } catch (error) {
      setAccountError(apiErrorMessage(error));
    } finally {
      setSavingAccount(false);
    }
  }

  async function handleLogout() {
    await logout();
    navigate('/');
  }

  if (!user) return null;

  return (
    <div className="container-page py-8">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink-200 pb-6 dark:border-ink-800">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-ink-900 font-display text-xl font-black text-white dark:bg-white dark:text-ink-900">
            {initials(user.username)}
          </div>
          <div>
            <p className="eyebrow">Your account</p>
            <h1 className="mt-0.5 text-3xl font-bold tracking-tight">
              {user.first_name || user.username}
            </h1>
            <p className="mt-1 text-sm text-ink-500">
              @{user.username} · joined {formatDate(user.date_joined)}
              {user.is_staff && (
                <span className="ml-2 rounded-full bg-signal-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-600 dark:text-teal-300">
                  Staff
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {user.is_staff && <Link to="/admin" className="btn-secondary btn-sm">Admin dashboard</Link>}
          <button type="button" onClick={handleLogout} className="btn-secondary btn-sm">
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      </header>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {[
          { label: 'Saved articles', value: saved.data?.count ?? '—', icon: Bookmark, to: '/saved' },
          { label: 'Fact checks run', value: checks.data?.count ?? '—', icon: ShieldQuestion, to: '/fact-check' },
          {
            label: 'Interests selected',
            value: preferences.data ? selected.length : '—',
            icon: Sparkles,
            to: null,
          },
        ].map((stat) => (
          <div key={stat.label} className="card flex items-center gap-3 p-4">
            <stat.icon className="h-5 w-5 text-accent-600" aria-hidden />
            <div>
              <p className="text-2xl font-bold leading-tight">{stat.value}</p>
              <p className="text-[11px] uppercase tracking-wider text-ink-400">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-bold">
                  <Sparkles className="h-4 w-4 text-signal-500" aria-hidden /> Your interests
                </h2>
                <p className="mt-1 text-sm leading-6 text-ink-500 dark:text-ink-400">
                  Preferred sections are boosted in recommendations and the “For you” rail.
                  The main feed still shows everything important.
                </p>
              </div>
              {prefsSaved && (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600">
                  <Check className="h-3.5 w-3.5" /> Saved
                </span>
              )}
            </div>

            {categories.loading && <div className="mt-4"><SkeletonLines count={3} /></div>}
            {categories.error && <div className="mt-4"><ErrorState compact message={categories.error} onRetry={categories.reload} /></div>}

            <div className="mt-4 flex flex-wrap gap-2">
              {(categories.data || []).map((category) => {
                const active = selected.includes(category.slug);
                return (
                  <button
                    key={category.slug}
                    type="button"
                    onClick={() => toggleCategory(category.slug)}
                    aria-pressed={active}
                    className={cx('chip', active && 'chip-active')}
                  >
                    {active && <Check className="h-3 w-3" aria-hidden />}
                    {category.name}
                  </button>
                );
              })}
            </div>

            <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-ink-200 p-3.5 dark:border-ink-700">
              <input
                type="checkbox"
                checked={personalize}
                onChange={(event) => {
                  setPersonalize(event.target.checked);
                  setPrefsSaved(false);
                }}
                className="mt-0.5 h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-500"
              />
              <span>
                <span className="block text-sm font-medium">Personalize my feed</span>
                <span className="mt-0.5 block text-xs leading-5 text-ink-500 dark:text-ink-400">
                  When off, recommendations use recency and reader engagement instead of
                  your interests and history.
                </span>
              </span>
            </label>

            {prefsError && <p className="mt-3 text-xs text-rose-600">{prefsError}</p>}

            <button
              type="button"
              onClick={savePreferences}
              disabled={savingPrefs}
              className="btn-primary mt-4"
            >
              {savingPrefs ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save interests
            </button>
          </section>

          <section className="card p-5 sm:p-6">
            <h2 className="flex items-center gap-2 text-lg font-bold">
              <UserRound className="h-4 w-4" aria-hidden /> Account details
            </h2>
            <form onSubmit={saveAccount} className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="first">First name</label>
                <input
                  id="first"
                  className="input"
                  value={account.first_name}
                  onChange={(event) => setAccount({ ...account, first_name: event.target.value })}
                />
              </div>
              <div>
                <label className="label" htmlFor="last">Last name</label>
                <input
                  id="last"
                  className="input"
                  value={account.last_name}
                  onChange={(event) => setAccount({ ...account, last_name: event.target.value })}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="label" htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  className="input"
                  value={account.email}
                  onChange={(event) => setAccount({ ...account, email: event.target.value })}
                />
              </div>
              {accountError && <p className="text-xs text-rose-600 sm:col-span-2">{accountError}</p>}
              <div className="sm:col-span-2">
                <button type="submit" className="btn-secondary" disabled={savingAccount}>
                  {savingAccount ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Update details
                </button>
              </div>
            </form>
          </section>

          <section className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5 dark:border-ink-800">
              <h2 className="flex items-center gap-2 text-lg font-bold">
                <ShieldQuestion className="h-4 w-4" aria-hidden /> Fact-check history
              </h2>
              <Link to="/fact-check" className="text-xs font-medium text-ink-500 hover:text-ink-900 dark:hover:text-white">
                New check
              </Link>
            </div>
            {checks.loading && <div className="p-5"><SkeletonLines count={3} /></div>}
            {!checks.loading && !checks.data?.results?.length && (
              <p className="p-5 text-sm text-ink-500">
                No claim checks yet. Paste a claim on the fact-check page to see the evidence
                NewsHub can retrieve.
              </p>
            )}
            {checks.data?.results?.length > 0 && (
              <ul className="divide-y divide-ink-100 dark:divide-ink-800">
                {checks.data.results.map((entry) => {
                  const style = VERDICT_STYLES[entry.verdict] || VERDICT_STYLES.insufficient;
                  return (
                    <li key={entry.id} className="flex items-start justify-between gap-3 px-5 py-3">
                      <div>
                        <p className="line-clamp-2 text-sm">{entry.claim}</p>
                        <p className="mt-1 text-[11px] text-ink-400">
                          {timeAgo(entry.created_at)} · {percent(entry.confidence)} confidence
                        </p>
                      </div>
                      <span className={cx('shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize', style.tone)}>
                        {entry.verdict}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <aside className="space-y-5">
          <section className="card p-5">
            <h2 className="flex items-center gap-2 text-sm font-bold">
              <Bookmark className="h-4 w-4 text-accent-600" aria-hidden /> Saved recently
            </h2>
            {saved.loading && <div className="mt-3"><SkeletonLines count={4} /></div>}
            {!saved.loading && !saved.data?.results?.length && (
              <p className="mt-2 text-xs leading-5 text-ink-500">
                Nothing saved yet. Bookmark articles to build a reading list.
              </p>
            )}
            <ul className="mt-2 divide-y divide-ink-100 dark:divide-ink-800">
              {(saved.data?.results || []).slice(0, 5).map((article) => (
                <li key={article.id} className="py-2.5">
                  <Link to={`/article/${article.id}`} className="line-clamp-2 text-sm hover:text-accent-700 dark:hover:text-accent-300">
                    {article.title}
                  </Link>
                  <p className="mt-0.5 text-[10px] uppercase tracking-wider text-ink-400">{article.source}</p>
                </li>
              ))}
            </ul>
            <Link to="/saved" className="btn-secondary btn-sm mt-3 w-full">Open reading list</Link>
          </section>

          <section className="rounded-2xl border border-ink-200 bg-white p-5 dark:border-ink-800 dark:bg-ink-900">
            <h2 className="text-sm font-bold">Privacy</h2>
            <p className="mt-2 text-xs leading-5 text-ink-500 dark:text-ink-400">
              Saved articles and interactions are only used to rank your own recommendations.
              They are never shown publicly, and personalization can be switched off at any
              time.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
