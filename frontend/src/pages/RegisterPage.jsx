import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

function fieldError(raw, field) {
  const value = raw?.[field];
  if (Array.isArray(value)) return value[0];
  if (typeof value === 'string') return value;
  return '';
}

export default function RegisterPage() {
  useDocumentTitle('Create an account');
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [rawErrors, setRawErrors] = useState({});
  const [busy, setBusy] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setRawErrors({});
    if (form.password !== form.password_confirm) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    const result = await register({
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      password_confirm: form.password_confirm,
    });
    setBusy(false);
    if (result.ok) {
      navigate('/', { replace: true });
    } else {
      setRawErrors(result.raw || {});
      setError(result.error);
    }
  }

  const requirements = [
    { label: 'At least 8 characters', ok: form.password.length >= 8 },
    { label: 'Not entirely numeric', ok: form.password.length > 0 && !/^\d+$/.test(form.password) },
    { label: 'Passwords match', ok: form.password.length > 0 && form.password === form.password_confirm },
  ];

  return (
    <div className="container-page grid items-start gap-10 py-12 lg:grid-cols-2">
      <div className="mx-auto w-full max-w-md lg:order-2">
        <div className="card p-6 sm:p-8">
          <h1 className="text-2xl font-bold">Create your NewsHub account</h1>
          <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">
            Free, no newsletter spam. Preferences can be changed at any time.
          </p>

          {error && (
            <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {error}
            </div>
          )}

          <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
            <div>
              <label className="label" htmlFor="username">Username</label>
              <input
                id="username"
                className="input"
                autoComplete="username"
                required
                minLength={3}
                value={form.username}
                onChange={(event) => update('username', event.target.value)}
              />
              {fieldError(rawErrors, 'username') && (
                <p className="mt-1 text-[11px] text-rose-600">{fieldError(rawErrors, 'username')}</p>
              )}
            </div>
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                className="input"
                autoComplete="email"
                required
                value={form.email}
                onChange={(event) => update('email', event.target.value)}
              />
              {fieldError(rawErrors, 'email') && (
                <p className="mt-1 text-[11px] text-rose-600">{fieldError(rawErrors, 'email')}</p>
              )}
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  className="input pr-11"
                  autoComplete="new-password"
                  required
                  value={form.password}
                  onChange={(event) => update('password', event.target.value)}
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
              {fieldError(rawErrors, 'password') && (
                <p className="mt-1 text-[11px] text-rose-600">{fieldError(rawErrors, 'password')}</p>
              )}
            </div>
            <div>
              <label className="label" htmlFor="confirm">Confirm password</label>
              <input
                id="confirm"
                type={showPassword ? 'text' : 'password'}
                className="input"
                autoComplete="new-password"
                required
                value={form.password_confirm}
                onChange={(event) => update('password_confirm', event.target.value)}
              />
              {fieldError(rawErrors, 'password_confirm') && (
                <p className="mt-1 text-[11px] text-rose-600">{fieldError(rawErrors, 'password_confirm')}</p>
              )}
            </div>

            <ul className="space-y-1.5 rounded-xl bg-ink-50 p-3 dark:bg-ink-800/50">
              {requirements.map((requirement) => (
                <li
                  key={requirement.label}
                  className={
                    requirement.ok
                      ? 'flex items-center gap-1.5 text-[11px] text-emerald-700 dark:text-emerald-300'
                      : 'flex items-center gap-1.5 text-[11px] text-ink-400'
                  }
                >
                  <CheckCircle2 className="h-3 w-3" aria-hidden /> {requirement.label}
                </li>
              ))}
            </ul>

            <button type="submit" className="btn-primary w-full" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
              {busy ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-500">
            Already registered?{' '}
            <Link to="/login" className="font-semibold text-accent-700 hover:underline dark:text-accent-400">
              Sign in
            </Link>
          </p>
        </div>
      </div>

      <div className="hidden lg:block">
        <p className="eyebrow">Personalize</p>
        <h2 className="mt-2 font-display text-4xl font-bold leading-tight">
          News that follows your interests.
        </h2>
        <p className="mt-3 max-w-md text-sm leading-6 text-ink-500 dark:text-ink-400">
          NewsHub keeps the general feed intact while ranking a separate recommendation
          stream around the sections you choose. No tracking scripts, no third-party
          analytics.
        </p>
        <div className="mt-6 space-y-3 text-sm">
          {[
            'Choose from ten editorial sections',
            'Save articles to a private reading list',
            'See which stories an evidence check used',
            'Switch between light and dark reading modes',
          ].map((item) => (
            <p key={item} className="flex items-start gap-2 text-ink-600 dark:text-ink-300">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-signal-500" aria-hidden /> {item}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}
