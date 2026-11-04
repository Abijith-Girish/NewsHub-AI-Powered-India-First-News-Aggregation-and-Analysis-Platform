import { Loader2, ShieldAlert } from 'lucide-react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isStaff, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="container-page flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-ink-400" aria-label="Loading" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (adminOnly && !isStaff) {
    return (
      <div className="container-page flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <ShieldAlert className="h-10 w-10 text-accent-600" aria-hidden />
        <h1 className="text-3xl font-bold">Administrators only</h1>
        <p className="max-w-md text-sm text-ink-600 dark:text-ink-400">
          This dashboard manages published content and is restricted to staff
          accounts. Sign in with an administrator account to continue.
        </p>
        <Link to="/" className="btn-primary">
          Back to news
        </Link>
      </div>
    );
  }

  return children;
}
