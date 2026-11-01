import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { api } from '../lib/api.js';

const CompanyContext = createContext(null);
const COMPANY_KEY = 'portal_company';

export function CompanyProvider({ children }) {
  const { user } = useAuth();
  const memberships = useMemo(() => user?.memberships ?? [], [user]);
  const [selectedId, setSelectedId] = useState(() => Number(sessionStorage.getItem(COMPANY_KEY)) || null);
  const [company, setCompany] = useState(null);
  const [version, setVersion] = useState(0);

  const membership = memberships.find((m) => m.company_id === selectedId) ?? memberships[0] ?? null;
  const companyId = membership?.company_id ?? null;

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    api(`/api/companies/${companyId}`)
      .then((data) => {
        if (!cancelled) setCompany(data);
      })
      .catch(() => {
        if (!cancelled) setCompany(null);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, version]);

  const selectCompany = useCallback((id) => {
    sessionStorage.setItem(COMPANY_KEY, String(id));
    setSelectedId(id);
  }, []);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const value = useMemo(
    // During a switch the state still holds the previous company until the new one arrives.
    () => ({ memberships, company: company?.id === companyId ? company : null, membership, selectCompany, refresh }),
    [memberships, company, companyId, membership, selectCompany, refresh],
  );
  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompany() {
  return useContext(CompanyContext);
}
