import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, clearToken, getToken, setToken } from '../lib/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [token, setTokenState] = useState(getToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    api('/api/me')
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        // A 401 is already redirected by api(); anything else leaves the user signed out.
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(async (email, password) => {
    const result = await api('/api/login', {
      method: 'POST',
      body: { email, password },
      skipAuthRedirect: true,
    });
    setToken(result.access_token);
    setLoading(true);
    setTokenState(result.access_token);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    sessionStorage.removeItem('portal_company');
    setTokenState(null);
    setUser(null);
    setLoading(false);
    navigate('/login', { replace: true });
  }, [navigate]);

  const value = useMemo(
    () => ({ token, user, login, logout, loading }),
    [token, user, login, logout, loading],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
