import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { apiErrorMessage, authApi, tokenStore } from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));

  useEffect(() => {
    let active = true;
    if (!tokenStore.get()) {
      setLoading(false);
      return undefined;
    }
    authApi
      .profile()
      .then(({ data }) => {
        if (active) setUser(data);
      })
      .catch(() => {
        tokenStore.clear();
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (identifier, password) => {
    try {
      const { data } = await authApi.login({ identifier, password });
      tokenStore.set(data.token);
      setUser(data.user);
      return { ok: true, user: data.user };
    } catch (error) {
      return { ok: false, error: apiErrorMessage(error) };
    }
  }, []);

  const register = useCallback(async (payload) => {
    try {
      const { data } = await authApi.register(payload);
      tokenStore.set(data.token);
      setUser(data.user);
      return { ok: true, user: data.user };
    } catch (error) {
      return { ok: false, error: apiErrorMessage(error), raw: error.response?.data };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // A stale token is still cleared locally.
    }
    tokenStore.clear();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.get()) return null;
    try {
      const { data } = await authApi.profile();
      setUser(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      isStaff: Boolean(user?.is_staff),
      login,
      register,
      logout,
      refreshUser,
      setUser,
    }),
    [user, loading, login, register, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
