import {
  Bookmark,
  BarChart3,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Search,
  ShieldCheck,
  Sun,
  User,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { cx, initials } from '../lib/format';

const LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/explore', label: 'Explore' },
  { to: '/categories', label: 'Categories' },
  { to: '/fact-check', label: 'Fact Check' },
  { to: '/briefing', label: 'Daily Briefing' },
  { to: '/saved', label: 'Saved' },
];

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, isStaff, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [query, setQuery] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  useEffect(() => {
    setMenuOpen(false);
    setUserMenu(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    function onClick(event) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setUserMenu(false);
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  function submitSearch(event) {
    event.preventDefault();
    const value = query.trim();
    navigate(value ? `/explore?q=${encodeURIComponent(value)}` : '/explore');
    setMenuOpen(false);
  }

  async function handleLogout() {
    await logout();
    setUserMenu(false);
    navigate('/');
  }

  return (
    <header className="sticky top-0 z-40 border-b border-ink-200/80 bg-ink-50/90 backdrop-blur-md dark:border-ink-800 dark:bg-ink-950/90">
      <div className="hidden border-b border-ink-200/60 py-1.5 dark:border-ink-800/60 sm:block">
        <div className="container-page flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-ink-500 dark:text-ink-400">
          <span>
            {new Intl.DateTimeFormat('en', {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            }).format(new Date())}
          </span>
          <span className="flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            Aggregated from independent publishers · AI-assisted analysis
          </span>
        </div>
      </div>

      <div className="container-page flex h-16 items-center gap-3">
        <Link to="/" className="flex shrink-0 items-baseline gap-1.5" aria-label="NewsHub home">
          <span className="font-display text-2xl font-black tracking-tight text-ink-900 dark:text-white">
            News<span className="text-accent-600 dark:text-accent-400">Hub</span>
          </span>
          <span className="hidden rounded-full border border-ink-300 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-ink-500 dark:border-ink-600 dark:text-ink-400 sm:inline">
            AI
          </span>
        </Link>

        <nav className="ml-4 hidden items-center gap-1 lg:flex" aria-label="Primary">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                cx(
                  'rounded-full px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-ink-900 text-white dark:bg-white dark:text-ink-900'
                    : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-white'
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <form onSubmit={submitSearch} className="ml-auto hidden max-w-xs flex-1 md:block" role="search">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              aria-hidden
            />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search AI, politics, markets…"
              aria-label="Search news"
              className="w-full rounded-full border border-ink-200 bg-white py-2 pl-9 pr-3 text-sm placeholder:text-ink-400 focus:border-ink-400 focus:outline-none focus:ring-2 focus:ring-ink-900/10 dark:border-ink-700 dark:bg-ink-900 dark:text-white dark:placeholder:text-ink-500"
            />
          </div>
        </form>

        <div className="ml-auto flex items-center gap-1 md:ml-2">
          <button
            type="button"
            onClick={toggle}
            className="rounded-full p-2 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-white"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={isDark ? 'Light mode' : 'Dark mode'}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>

          {isAuthenticated ? (
            <div className="relative" ref={userMenuRef}>
              <button
                type="button"
                onClick={() => setUserMenu((open) => !open)}
                className="flex items-center gap-2 rounded-full border border-ink-200 py-1 pl-1 pr-2.5 text-sm font-medium hover:border-ink-400 dark:border-ink-700 dark:hover:border-ink-500"
                aria-haspopup="menu"
                aria-expanded={userMenu}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink-900 text-[11px] font-bold text-white dark:bg-white dark:text-ink-900">
                  {initials(user?.username)}
                </span>
                <span className="hidden max-w-[7rem] truncate sm:inline">
                  {user?.username}
                </span>
              </button>
              {userMenu && (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-52 overflow-hidden rounded-xl border border-ink-200 bg-white py-1 shadow-lift dark:border-ink-700 dark:bg-ink-900"
                >
                  <Link
                    to="/profile"
                    role="menuitem"
                    className="flex items-center gap-2 px-3.5 py-2 text-sm text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800"
                  >
                    <User className="h-4 w-4" /> Profile &amp; interests
                  </Link>
                  <Link
                    to="/truth-trace"
                    role="menuitem"
                    className="flex items-center gap-2 px-3.5 py-2 text-sm text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800"
                  >
                    <ShieldCheck className="h-4 w-4" /> Tracked claims
                  </Link>
                  <Link
                    to="/analytics"
                    role="menuitem"
                    className="flex items-center gap-2 px-3.5 py-2 text-sm text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800"
                  >
                    <BarChart3 className="h-4 w-4" /> Reading analytics
                  </Link>
                  <Link
                    to="/saved"
                    role="menuitem"
                    className="flex items-center gap-2 px-3.5 py-2 text-sm text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800"
                  >
                    <Bookmark className="h-4 w-4" /> Saved articles
                  </Link>
                  {isStaff && (
                    <Link
                      to="/admin"
                      role="menuitem"
                      className="flex items-center gap-2 px-3.5 py-2 text-sm text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800"
                    >
                      <LayoutDashboard className="h-4 w-4" /> Admin dashboard
                    </Link>
                  )}
                  <button
                    type="button"
                    role="menuitem"
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 border-t border-ink-100 px-3.5 py-2 text-left text-sm text-ink-700 hover:bg-ink-50 dark:border-ink-800 dark:text-ink-200 dark:hover:bg-ink-800"
                  >
                    <LogOut className="h-4 w-4" /> Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Link to="/login" className="btn-ghost text-sm">
                Sign in
              </Link>
              <Link to="/register" className="btn-primary btn-sm">
                Get started
              </Link>
            </div>
          )}

          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="rounded-full p-2 text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800 lg:hidden"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <div className="border-t border-ink-200 bg-ink-50 px-4 py-4 dark:border-ink-800 dark:bg-ink-950 lg:hidden">
          <form onSubmit={submitSearch} className="relative mb-3" role="search">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search any topic…"
              aria-label="Search news"
              className="input pl-9"
            />
          </form>
          <nav className="grid gap-1" aria-label="Mobile">
            {LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cx(
                    'rounded-lg px-3 py-2 text-sm font-medium',
                    isActive
                      ? 'bg-ink-900 text-white dark:bg-white dark:text-ink-900'
                      : 'text-ink-700 hover:bg-ink-100 dark:text-ink-200 dark:hover:bg-ink-800'
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
            {isStaff && (
              <NavLink
                to="/admin"
                className="rounded-lg px-3 py-2 text-sm font-medium text-ink-700 hover:bg-ink-100 dark:text-ink-200 dark:hover:bg-ink-800"
              >
                Admin dashboard
              </NavLink>
            )}
          </nav>
          {!isAuthenticated && (
            <div className="mt-3 flex gap-2">
              <Link to="/login" className="btn-secondary flex-1">
                Sign in
              </Link>
              <Link to="/register" className="btn-primary flex-1">
                Register
              </Link>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
