import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, clearToken, getToken, setToken } from '../lib/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [token, setTokenState] = useState(getToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));
  const [loadFailed, setLoadFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    api('/api/me')
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((err) => {
        if (cancelled) return;
        setUser(null);
        // A 401 is already redirected by api(). Anything else needs a way out of the loading screen.
        if (err.status !== 401) setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, attempt]);

  const retry = useCallback(() => {
    setLoadFailed(false);
    setLoading(true);
    setAttempt((value) => value + 1);
  }, []);

  const login = useCallback(async (email, password) => {
    const result = await api('/api/login', {
      method: 'POST',
      body: { email, password },
      skipAuthRedirect: true,
    });
    setToken(result.access_token);
    setLoadFailed(false);
    setLoading(true);
    setTokenState(result.access_token);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    sessionStorage.removeItem('portal_company');
    setTokenState(null);
    setUser(null);
    setLoading(false);
    setLoadFailed(false);
    navigate('/login', { replace: true });
  }, [navigate]);

  const changePassword = useCallback(async (currentPassword, newPassword) => {
    // A 401 here means a wrong current password, which must not end the session.
    await api('/api/me/password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
      skipAuthRedirect: true,
    });
    setUser((current) => current && { ...current, must_change_password: false });
  }, []);

  const value = useMemo(
    () => ({ token, user, login, logout, loading, loadFailed, retry, changePassword }),
    [token, user, login, logout, loading, loadFailed, retry, changePassword],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
