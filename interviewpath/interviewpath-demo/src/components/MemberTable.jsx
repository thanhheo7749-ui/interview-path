import { Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api.js';

const ROLES = ['hr', 'manager', 'employee'];
const inputClass =
  'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:border-blue-500';
const primaryButton =
  'rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-card transition hover:bg-blue-700 disabled:opacity-60';

function MemberTable({ companyId, departments }) {
  const { t } = useTranslation();
  const [members, setMembers] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('employee');
  const [departmentId, setDepartmentId] = useState('');

  const base = `/api/companies/${companyId}/members`;

  const load = useCallback(async () => {
    try {
      setMembers(await api(`/api/companies/${companyId}/members`));
    } catch (err) {
      setError(err.message);
    }
  }, [companyId]);

  useEffect(() => {
    let cancelled = false;
    api(`/api/companies/${companyId}/members`)
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const add = async (event) => {
    event.preventDefault();
    setError('');
    setNotice(null);
    setBusy(true);
    try {
      const created = await api(base, {
        method: 'POST',
        body: {
          email: email.trim(),
          full_name: fullName.trim() || null,
          role,
          department_id: departmentId === '' ? null : Number(departmentId),
        },
      });
      setNotice({
        email: created.email,
        temporaryPassword: created.temporary_password ?? null,
        existingAccount: created.existing_account === true,
      });
      setEmail('');
      setFullName('');
      setRole('employee');
      setDepartmentId('');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const patch = async (member, changes) => {
    setError('');
    try {
      await api(`${base}/${member.id}`, { method: 'PATCH', body: changes });
      await load();
    } catch (err) {
      setError(err.message);
      await load();
    }
  };

  const remove = async (member) => {
    if (!window.confirm(t('members.confirmRemove'))) return;
    setError('');
    try {
      await api(`${base}/${member.id}`, { method: 'DELETE' });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const roleLabel = (value) => t(`members.roles.${value}`);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <h2 className="text-lg font-extrabold tracking-tight">{t('members.title')}</h2>

      {error && (
        <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
          {error}
        </p>
      )}

      {notice && (
        <div role="status" className="mt-3 space-y-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {notice.temporaryPassword && (
            <div>
              <p className="font-bold">{t('members.temporaryPassword')}</p>
              <p className="mt-1">
                {notice.email}: <code className="rounded bg-white px-2 py-1 font-mono">{notice.temporaryPassword}</code>
              </p>
            </div>
          )}
          {notice.existingAccount && <p className="font-semibold">{t('members.existingAccount')}</p>}
          <button type="button" onClick={() => setNotice(null)} className="text-xs font-bold underline">
            {t('common.dismiss')}
          </button>
        </div>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs font-bold uppercase tracking-[0.12em] text-slate-400">
              <th className="py-2 pr-3">{t('members.colEmail')}</th>
              <th className="py-2 pr-3">{t('members.colName')}</th>
              <th className="py-2 pr-3">{t('members.colRole')}</th>
              <th className="py-2 pr-3">{t('members.colDepartment')}</th>
              <th className="py-2">
                <span className="sr-only">{t('common.remove')}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.id} className="border-b border-slate-100">
                <td className="py-2 pr-3 font-semibold text-slate-900">{member.email}</td>
                <td className="py-2 pr-3 text-slate-600">{member.full_name}</td>
                <td className="py-2 pr-3">
                  <select
                    aria-label={`${t('members.colRole')} ${member.email}`}
                    value={member.role}
                    onChange={(e) => patch(member, { role: e.target.value })}
                    className={inputClass}
                  >
                    {ROLES.map((value) => (
                      <option key={value} value={value}>
                        {roleLabel(value)}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-3">
                  <select
                    aria-label={`${t('members.colDepartment')} ${member.email}`}
                    value={member.department_id ?? ''}
                    onChange={(e) =>
                      patch(member, { department_id: e.target.value === '' ? null : Number(e.target.value) })
                    }
                    className={inputClass}
                  >
                    <option value="">{t('members.noDepartment')}</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    title={t('common.remove')}
                    aria-label={t("common.remove")}
                    onClick={() => remove(member)}
                    className="rounded-lg p-1 text-slate-400 hover:bg-red-50 hover:text-red-700"
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form onSubmit={add} className="mt-5 flex flex-wrap items-end gap-3">
        <label className="text-sm font-semibold text-slate-700">
          <span className="block">{t('members.email')}</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={`${inputClass} mt-1`} />
        </label>
        <label className="text-sm font-semibold text-slate-700">
          <span className="block">{t('members.name')}</span>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} className={`${inputClass} mt-1`} />
        </label>
        <label className="text-sm font-semibold text-slate-700">
          <span className="block">{t('members.role')}</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} className={`${inputClass} mt-1`}>
            {ROLES.map((value) => (
              <option key={value} value={value}>
                {roleLabel(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700">
          <span className="block">{t('members.department')}</span>
          <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} className={`${inputClass} mt-1`}>
            <option value="">{t('members.noDepartment')}</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy} className={primaryButton}>
          {t('members.add')}
        </button>
      </form>
    </section>
  );
}

export default MemberTable;
