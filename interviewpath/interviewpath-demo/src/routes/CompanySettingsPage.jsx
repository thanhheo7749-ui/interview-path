import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import DepartmentTree from '../components/DepartmentTree.jsx';
import MemberTable from '../components/MemberTable.jsx';
import { api } from '../lib/api.js';

function CompanySettingsPage() {
  const { company, membership } = useCompany();
  const { t } = useTranslation();
  const [departments, setDepartments] = useState([]);
  const [version, setVersion] = useState(0);
  const companyId = membership?.company_id ?? null;
  const isHr = membership?.role === 'hr';

  const loadDepartments = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    api(`/api/companies/${companyId}/departments`)
      .then((data) => {
        if (!cancelled) setDepartments(data);
      })
      .catch(() => {
        if (!cancelled) setDepartments([]);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, version]);

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('settings.title')}</h1>

      {companyId == null ? (
        <p className="rounded-2xl border border-slate-200 bg-white p-6 text-sm font-semibold text-slate-600 shadow-card">
          {t('settings.noCompany')}
        </p>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">{t('settings.companyName')}</p>
            <p className="mt-1 text-lg font-extrabold text-slate-950">{company?.name ?? membership.company_name}</p>
            {!isHr && <p className="mt-2 text-sm text-slate-500">{t('settings.readOnlyNote')}</p>}
          </section>

          <DepartmentTree
            key={`departments-${companyId}`}
            companyId={companyId}
            departments={departments}
            canEdit={isHr}
            onChanged={loadDepartments}
          />
          {isHr && <MemberTable key={`members-${companyId}`} companyId={companyId} departments={departments} />}
        </>
      )}
    </div>
  );
}

export default CompanySettingsPage;
