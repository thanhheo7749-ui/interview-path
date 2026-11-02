import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import {
  createHiringRequest, generateDraft, listDepartments, listHiringRequests, listMembers,
} from '../lib/bridges.js';
import { listRoleOptions } from '../lib/jobs.js';

const INTAKE_OPEN = ['open', 'intake_in_progress', 'intake_empty'];

function CreateForm({ companyId, onCreated }) {
  const { t } = useTranslation();
  const [managers, setManagers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [title, setTitle] = useState('');
  const [managerId, setManagerId] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listMembers(companyId), listDepartments(companyId)])
      .then(([members, depts]) => {
        if (cancelled) return;
        setManagers(members.filter((m) => m.role === 'manager'));
        setDepartments(depts);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await createHiringRequest(companyId, {
        title: title.trim(),
        manager_user_id: Number(managerId),
        department_id: departmentId === '' ? null : Number(departmentId),
      });
      setTitle('');
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className={`${cardClass} space-y-3`}>
      <h2 className="font-bold">{t('bridges.requests.new')}</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm font-semibold text-slate-700">
          {t('bridges.requests.titleLabel')}
          <input required value={title} onChange={(e) => setTitle(e.target.value)} className={`${inputClass} mt-1 w-full`} />
        </label>
        <label className="text-sm font-semibold text-slate-700">
          {t('bridges.requests.managerLabel')}
          <select required value={managerId} onChange={(e) => setManagerId(e.target.value)} className={`${inputClass} mt-1 w-full`}>
            <option value="">{t('bridges.requests.chooseManager')}</option>
            {managers.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name || m.email}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700">
          {t('bridges.requests.departmentLabel')}
          <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} className={`${inputClass} mt-1 w-full`}>
            <option value="">{t('members.noDepartment')}</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {managers.length === 0 && <p className="text-sm text-slate-500">{t('bridges.requests.noManagers')}</p>}
      <ErrorAlert message={error} />
      <button type="submit" disabled={busy || !title.trim() || managerId === ''} className={primaryButton}>
        {t('bridges.requests.create')}
      </button>
    </form>
  );
}

// HR makes the first job description draft of a request from the company knowledge, optionally around one role.
function DraftActions({ companyId, request, roles }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [roleId, setRoleId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const existing = request.latest_draft_id;

  const generate = async () => {
    setError('');
    setBusy(true);
    try {
      const draft = await generateDraft(companyId, request.id, roleId === '' ? null : Number(roleId));
      navigate(`/jd-studio/${draft.id}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label={`${t('bridges.requests.roleLabel')}: ${request.title}`}
          value={roleId}
          onChange={(e) => setRoleId(e.target.value)}
          className={inputClass}
        >
          <option value="">{t('bridges.requests.anyRole')}</option>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.title}
            </option>
          ))}
        </select>
        <button type="button" disabled={busy} onClick={generate} className={primaryButton}>
          {t('bridges.requests.generateDraft')}
        </button>
        {existing != null && (
          <Link to={`/jd-studio/${existing}`} data-testid="open-draft" className={secondaryButton}>
            {t('bridges.requests.openDraft')}
          </Link>
        )}
      </div>
      <ErrorAlert message={error} />
    </div>
  );
}

// A manager reaches the draft of their own request here; it says so when their approval is what the draft waits for.
function ManagerDraftLink({ request }) {
  const { t } = useTranslation();
  const waiting = request.latest_draft_status === 'manager_review';
  return (
    <div className="flex flex-wrap items-center gap-3">
      {waiting && (
        <span data-testid="awaiting-approval" className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-900">
          {t('bridges.requests.awaitingApproval')}
        </span>
      )}
      <Link to={`/jd-studio/${request.latest_draft_id}`} data-testid="open-draft" className={waiting ? primaryButton : secondaryButton}>
        {t('bridges.requests.openDraft')}
      </Link>
    </div>
  );
}

function HiringRequestsPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const isHr = membership?.role === 'hr';
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);
  const [roles, setRoles] = useState([]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    listHiringRequests(companyId)
      .then((data) => {
        if (!cancelled) setRequests(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, version]);

  useEffect(() => {
    if (companyId == null || !isHr) return undefined;
    let cancelled = false;
    listRoleOptions(companyId)
      .then((data) => {
        if (!cancelled) setRoles(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [companyId, isHr]);

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('bridges.requests.title')}</h1>
      <ErrorAlert message={error} />
      {isHr && <CreateForm key={`create-${companyId}`} companyId={companyId} onCreated={reload} />}
      {requests && requests.length === 0 && <EmptyState>{t('bridges.requests.empty')}</EmptyState>}
      {requests && requests.length > 0 && (
        <ul className="space-y-3">
          {requests.map((request) => (
            <li key={request.id} data-testid={`request-${request.id}`} className={`${cardClass} flex items-center justify-between gap-4`}>
              <div>
                <p className="font-bold">{request.title}</p>
                <p data-testid="request-status" className="text-sm text-slate-600">
                  {t(`bridges.requests.status.${request.status}`, { defaultValue: request.status })}
                </p>
              </div>
              {isHr && <DraftActions companyId={companyId} request={request} roles={roles} />}
              {!isHr && request.latest_draft_id != null && <ManagerDraftLink request={request} />}
              {!isHr && INTAKE_OPEN.includes(request.status) && (
                <Link to={`/intake/${request.id}`} className={primaryButton}>
                  {request.status === 'intake_in_progress' ? t('bridges.requests.resumeIntake') : request.status === 'intake_empty' ? t('bridges.requests.startAgain') : t('bridges.requests.startIntake')}
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default HiringRequestsPage;
