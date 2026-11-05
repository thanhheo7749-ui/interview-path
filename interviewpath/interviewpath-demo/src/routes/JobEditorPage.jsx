import { Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import ChannelLinks from '../components/ChannelLinks.jsx';
import InterviewWindowFields, { isoToLocalInput, localInputToIso } from '../components/InterviewWindowFields.jsx';
import { ErrorAlert, WarningList, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { api } from '../lib/api.js';
import {
  DEFAULT_CHANNELS, INTERVIEW_LANGUAGES, NO_PUBLIC_REQUIREMENT, REQUIREMENT_VISIBILITIES, addChannels, closeJob, createJob, getJob, getPrefill,
  listRoleOptions, patchJob, publishJob,
} from '../lib/jobs.js';

let rowCounter = 0;
const newRow = (row = {}) => ({
  key: `row-${(rowCounter += 1)}`,
  text: row.text ?? '',
  must_have: Boolean(row.must_have),
  visibility: row.visibility ?? 'public',
  node_id: row.node_id ?? null,
});

// What the server stores about a requirement. Used to tell whether the requirements changed.
const signature = (rows) => JSON.stringify(rows.filter((r) => r.text.trim()).map((r) => [r.text.trim(), r.must_have, r.visibility, r.node_id]));
const toPayload = (rows) =>
  rows.filter((r) => r.text.trim()).map((r) => ({ text: r.text.trim(), must_have: r.must_have, visibility: r.visibility, node_id: r.node_id }));

function JobEditor() {
  const { t } = useTranslation();
  const { jobId } = useParams();
  const isNew = jobId === undefined;
  const navigate = useNavigate();
  const location = useLocation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(!isNew);
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);
  const [error, setError] = useState(location.state?.error ?? '');
  const [studioDraft, setStudioDraft] = useState(null); // the JD Studio draft this job was made in
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  // Texts the automatic discrimination check could not look at: saved, but HR should read them.
  const [warnings, setWarnings] = useState(location.state?.warnings ?? []);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [roleNodeId, setRoleNodeId] = useState('');
  const [languages, setLanguages] = useState(['en']);
  const [schedulingEnabled, setSchedulingEnabled] = useState(false);
  const [windowStart, setWindowStart] = useState('');
  const [windowEnd, setWindowEnd] = useState('');
  const [rows, setRows] = useState([]);
  const [loadedSignature, setLoadedSignature] = useState(signature([]));

  const applyJob = useCallback((data) => {
    const loaded = data.requirements.map(newRow);
    setJob(data);
    setLoadedSignature(signature(loaded));
    setTitle(data.title);
    setDescription(data.description);
    setDepartmentId(data.department_id == null ? '' : String(data.department_id));
    setRoleNodeId(data.role_node_id == null ? '' : String(data.role_node_id));
    setLanguages(data.interview_languages);
    setSchedulingEnabled(Boolean(data.scheduling_enabled));
    setWindowStart(isoToLocalInput(data.interview_window_start));
    setWindowEnd(isoToLocalInput(data.interview_window_end));
    setRows(loaded);
  }, []);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    api(`/api/companies/${companyId}/departments`)
      .then((data) => {
        if (!cancelled) setDepartments(data);
      })
      .catch(() => {});
    if (isNew) {
      listRoleOptions(companyId)
        .then((data) => {
          if (!cancelled) setRoles(data);
        })
        .catch((err) => {
          if (!cancelled) setError(err.message);
        });
    } else {
      getJob(companyId, jobId)
        .then((data) => {
          if (cancelled) return;
          applyJob(data);
          setLoading(false);
        })
        .catch((err) => {
          if (cancelled) return;
          setError(err.message);
          setLoading(false);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [companyId, jobId, isNew, applyJob]);

  const status = job?.status ?? 'draft';
  const readOnly = status === 'closed';
  const requirementsChanged = signature(rows) !== loadedSignature;
  const visibleRoles = useMemo(
    () => roles.filter((r) => departmentId === '' || String(r.department_id) === departmentId),
    [roles, departmentId],
  );

  const chooseRole = async (value) => {
    setRoleNodeId(value);
    setError('');
    if (value === '') return;
    try {
      const prefill = await getPrefill(companyId, Number(value));
      setTitle(prefill.title);
      setDescription(prefill.description);
      setDepartmentId(prefill.department_id == null ? '' : String(prefill.department_id));
      setRows(prefill.requirements.map(newRow));
    } catch (err) {
      setError(err.message);
    }
  };

  const chooseDepartment = (value) => {
    setDepartmentId(value);
    const current = roles.find((r) => String(r.id) === roleNodeId);
    if (current && value !== '' && String(current.department_id) !== value) setRoleNodeId('');
  };

  const updateRow = (key, changes) => setRows((current) => current.map((r) => (r.key === key ? { ...r, ...changes } : r)));
  const toggleLanguage = (language) =>
    setLanguages((current) => (current.includes(language) ? current.filter((l) => l !== language) : [...current, language]));

  // Saves the form and returns the stored job. Creating navigates to the new job's page once everything is done.
  const persist = async () => {
    const department = departmentId === '' ? null : Number(departmentId);
    const windowFields = {
      scheduling_enabled: schedulingEnabled,
      interview_window_start: localInputToIso(windowStart),
      interview_window_end: localInputToIso(windowEnd),
      interview_window_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
    if (isNew) {
      return createJob(companyId, {
        title: title.trim(), description, department_id: department, role_node_id: roleNodeId === '' ? null : Number(roleNodeId),
        interview_languages: languages, requirements: toPayload(rows), ...windowFields,
      });
    }
    return patchJob(companyId, job.id, {
      title: title.trim(), description, department_id: department, interview_languages: languages, requirements: toPayload(rows),
      ...windowFields,
    });
  };

  const run = async (publish) => {
    if (!title.trim()) {
      setError(t('jobs.titleRequired'));
      return;
    }
    if (languages.length === 0) {
      setError(t('jobs.languageRequired'));
      return;
    }
    if (schedulingEnabled && (!windowStart || !windowEnd || new Date(windowStart) >= new Date(windowEnd))) {
      setError(t('jobs.windowInvalid'));
      return;
    }
    setError('');
    setSaved(false);
    setWarnings([]);
    setBusy(true);
    let stored = null;
    let found = [];
    try {
      stored = await persist();
      found = stored.warnings ?? [];
      if (publish) {
        stored = await publishJob(companyId, stored.id);
        found = [...found, ...(stored.warnings ?? [])];
        await addChannels(companyId, stored.id, DEFAULT_CHANNELS);
        stored = await getJob(companyId, stored.id);
      }
      if (isNew) {
        navigate(`/jobs/${stored.id}`, { replace: true, state: { warnings: found } });
      } else {
        applyJob(stored);
        setWarnings(found);
        setSaved(true);
      }
    } catch (err) {
      if (isNew && stored) navigate(`/jobs/${stored.id}`, { replace: true, state: { error: err.message, warnings: found } });
      else if (err.code === 'description_in_jd_studio') {
        setStudioDraft(err.data?.draft_id ?? null);
        setError(t('jobs.descriptionInJdStudio'));
      } else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const close = async () => {
    if (!window.confirm(t('jobs.confirmClose'))) return;
    setError('');
    setBusy(true);
    try {
      await closeJob(companyId, job.id);
      applyJob(await getJob(companyId, job.id));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const addChannel = async (channel) => {
    await addChannels(companyId, job.id, [channel]);
    applyJob(await getJob(companyId, job.id));
  };

  if (loading) return <p className="p-8 text-sm font-semibold text-slate-500">{t('common.loading')}</p>;
  if (!isNew && !job) {
    return (
      <div className="space-y-4 p-8">
        <ErrorAlert message={error} />
        <Link to="/jobs" className={secondaryButton}>
          {t('jobs.back')}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-extrabold tracking-tight">{isNew ? t('jobs.newTitle') : t('jobs.editTitle')}</h1>
        {!isNew && (
          <span data-testid="job-status" className="rounded-full bg-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-slate-700">
            {t(`jobs.status.${status}`, { defaultValue: status })} {t('jobs.versionLabel', { version: job.version })}
          </span>
        )}
      </div>
      <ErrorAlert message={error} />
      {studioDraft != null && (
        <Link to={`/jd-studio/${studioDraft}`} data-testid="open-jd-studio" className={secondaryButton}>
          {t('jobs.openJdStudio')}
        </Link>
      )}
      <WarningList
        warnings={warnings.map((warning) => (warning === NO_PUBLIC_REQUIREMENT ? t('jobs.noPublicRequirement') : warning))}
        onDismiss={() => setWarnings([])}
      />
      {saved && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-900">
          {t('jobs.saved')}
        </p>
      )}
      {readOnly && <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">{t('jobs.closedNotice')}</p>}

      <section className={`${cardClass} space-y-4`}>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('jobs.department')}</span>
            <select value={departmentId} disabled={readOnly} onChange={(e) => chooseDepartment(e.target.value)} className={`${inputClass} mt-1`}>
              <option value="">{t('jobs.anyDepartment')}</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          {isNew && (
            <label className="text-sm font-semibold text-slate-700">
              <span className="block">{t('jobs.role')}</span>
              <select value={roleNodeId} onChange={(e) => chooseRole(e.target.value)} className={`${inputClass} mt-1`}>
                <option value="">{t('jobs.noRole')}</option>
                {visibleRoles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="min-w-64 flex-1 text-sm font-semibold text-slate-700">
            <span className="block">{t('jobs.jobTitle')}</span>
            <input value={title} disabled={readOnly} maxLength={255} onChange={(e) => setTitle(e.target.value)} className={`${inputClass} mt-1 w-full`} />
          </label>
        </div>
        {isNew && <p className="text-xs text-slate-500">{t('jobs.roleHint')}</p>}

        <label className="block text-sm font-semibold text-slate-700">
          <span className="block">{t('jobs.description')}</span>
          <textarea value={description} disabled={readOnly} rows={6} onChange={(e) => setDescription(e.target.value)} className={`${inputClass} mt-1 w-full`} />
        </label>
        <p className="text-xs text-slate-500">{t('jobs.descriptionHint')}</p>

        <fieldset>
          <legend className="text-sm font-semibold text-slate-700">{t('jobs.languages')}</legend>
          <div className="mt-1 flex flex-wrap gap-4">
            {INTERVIEW_LANGUAGES.map((language) => (
              <label key={language} className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <input type="checkbox" checked={languages.includes(language)} disabled={readOnly} onChange={() => toggleLanguage(language)} />
                {t(`jobs.language.${language}`)}
              </label>
            ))}
          </div>
        </fieldset>

        <InterviewWindowFields
          enabled={schedulingEnabled}
          start={windowStart}
          end={windowEnd}
          readOnly={readOnly}
          onEnabled={setSchedulingEnabled}
          onStart={setWindowStart}
          onEnd={setWindowEnd}
        />
      </section>

      <section className={`${cardClass} space-y-3`}>
        <h2 className="text-lg font-extrabold tracking-tight">{t('jobs.requirements')}</h2>
        {status === 'published' && requirementsChanged && (
          <p role="note" className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
            {t('jobs.versionNotice')}
          </p>
        )}
        {rows.length === 0 && <p className="text-sm font-semibold text-slate-600">{t('jobs.noRequirements')}</p>}
        <ul className="space-y-2">
          {rows.map((row, index) => (
            <li key={row.key} data-testid="requirement-row" className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <input
                aria-label={`${t('jobs.requirementText')} ${index + 1}`}
                value={row.text}
                disabled={readOnly}
                maxLength={2000}
                onChange={(e) => updateRow(row.key, { text: e.target.value })}
                className={`${inputClass} min-w-64 flex-1`}
              />
              <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <input
                  type="checkbox"
                  aria-label={`${t('jobs.mustHave')} ${index + 1}`}
                  checked={row.must_have}
                  disabled={readOnly}
                  onChange={(e) => updateRow(row.key, { must_have: e.target.checked })}
                />
                {t('jobs.mustHave')}
              </label>
              <select
                aria-label={`${t('jobs.visibility')} ${index + 1}`}
                value={row.visibility}
                disabled={readOnly}
                onChange={(e) => updateRow(row.key, { visibility: e.target.value })}
                className={inputClass}
              >
                {REQUIREMENT_VISIBILITIES.map((v) => (
                  <option key={v} value={v}>
                    {t(`layers.${v}`)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={readOnly}
                aria-label={`${t('common.remove')} ${index + 1}`}
                onClick={() => setRows((current) => current.filter((r) => r.key !== row.key))}
                className={secondaryButton}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
        <button type="button" disabled={readOnly} onClick={() => setRows((current) => [...current, newRow()])} className={`${secondaryButton} flex items-center gap-2`}>
          <Plus size={14} />
          {t('jobs.addRequirement')}
        </button>
        <p className="text-xs text-slate-500">{t('jobs.visibilityHint')}</p>
      </section>

      {!readOnly && (
        <div className="flex flex-wrap gap-3">
          {status === 'draft' ? (
            <>
              <button type="button" disabled={busy} onClick={() => run(false)} className={secondaryButton}>
                {t('jobs.saveDraft')}
              </button>
              <button type="button" disabled={busy} onClick={() => run(true)} className={primaryButton}>
                {t('jobs.publish')}
              </button>
            </>
          ) : (
            <>
              <button type="button" disabled={busy} onClick={() => run(false)} className={primaryButton}>
                {t('jobs.saveChanges')}
              </button>
              <button type="button" disabled={busy} onClick={close} className={secondaryButton}>
                {t('jobs.close')}
              </button>
            </>
          )}
        </div>
      )}

      {job?.slug && <ChannelLinks slug={job.slug} channels={job.channels} onAdd={addChannel} />}
    </div>
  );
}

// The key remounts the editor when moving between "new" and an existing job.
function JobEditorPage() {
  const { jobId } = useParams();
  return <JobEditor key={jobId ?? 'new'} />;
}

export default JobEditorPage;
