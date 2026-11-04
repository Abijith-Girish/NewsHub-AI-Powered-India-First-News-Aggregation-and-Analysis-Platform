import { AlertCircle, Eye, EyeOff, Loader2, LogIn } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export default function LoginPage() {
  useDocumentTitle('Sign in');
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [form, setForm] = useState({ identifier: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (isAuthenticated) {
    return (
      <div className="container-page py-20 text-center">
        <h1 className="text-2xl font-bold">You are already signed in</h1>
        <Link to="/" className="btn-primary mt-4">Go to the home page</Link>
      </div>
    );
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const result = await login(form.identifier.trim(), form.password);
    setBusy(false);
    if (result.ok) {
      navigate(from, { replace: true });
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="container-page grid items-center gap-10 py-12 lg:grid-cols-2">
      <div className="hidden lg:block">
        <p className="eyebrow">Welcome back</p>
        <h1 className="mt-2 font-display text-4xl font-bold leading-tight">
          Your briefing is waiting.
        </h1>
        <p className="mt-3 max-w-md text-sm leading-6 text-ink-500 dark:text-ink-400">
          Sign in to save articles, choose the sections you follow and get a feed ranked
          around your reading. Your preferences stay on the server, not in the browser.
        </p>
        <ul className="mt-6 space-y-3 text-sm text-ink-600 dark:text-ink-300">
          <li>· Personalized recommendations using TF-IDF similarity</li>
          <li>· Saved reading list across devices</li>
          <li>· Fact-check history for signed-in checks</li>
        </ul>
      </div>

      <div className="mx-auto w-full max-w-md">
        <div className="card p-6 sm:p-8">
          <h2 className="text-2xl font-bold">Sign in</h2>
          <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">
            Use your username or email address.
          </p>

          {error && (
            <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {error}
            </div>
          )}

          <form onSubmit={submit} className="mt-5 space-y-4">
            <div>
              <label className="label" htmlFor="identifier">Username or email</label>
              <input
                id="identifier"
                className="input"
                autoComplete="username"
                required
                value={form.identifier}
                onChange={(event) => setForm({ ...form, identifier: event.target.value })}
              />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  className="input pr-11"
                  autoComplete="current-password"
                  required
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-ink-400 hover:text-ink-700 dark:hover:text-white"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <button type="submit" className="btn-primary w-full" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-500">
            New to NewsHub?{' '}
            <Link to="/register" className="font-semibold text-accent-700 hover:underline dark:text-accent-400">
              Create an account
            </Link>
          </p>
        </div>
        <p className="mt-4 text-center text-[11px] leading-5 text-ink-400">
          Protected endpoints use server-side permission checks. Passwords are hashed by
          Django and never stored in plain text.
        </p>
      </div>
    </div>
  );
}
