import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { api } from '../lib/api.js';
import { getJob, listDocuments, notifyKbChanged, retryJob, uploadDocument } from '../lib/kb.js';

const VISIBILITIES = ['public', 'internal', 'confidential'];
const ACTIVE_JOB = ['queued', 'running'];
const POLL_MS = 1500;

function DocumentsPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [documents, setDocuments] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [visibility, setVisibility] = useState('internal');
  const [departmentId, setDepartmentId] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');

  const reload = useCallback(async () => {
    try {
      setDocuments(await listDocuments(companyId));
    } catch (err) {
      setError(err.message);
    }
  }, [companyId]);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    listDocuments(companyId)
      .then((data) => {
        if (!cancelled) setDocuments(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    api(`/api/companies/${companyId}/departments`)
      .then((data) => {
        if (!cancelled) setDepartments(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  // Poll every job that is still running. The key changes only when the set of running jobs changes.
  const activeJobKey = documents
    .filter((d) => d.job && ACTIVE_JOB.includes(d.job.status))
    .map((d) => d.job.id)
    .join(',');
  useEffect(() => {
    if (!activeJobKey || companyId == null) return undefined;
    const ids = activeJobKey.split(',').map(Number);
    let cancelled = false;
    const timer = setInterval(async () => {
      const jobs = await Promise.all(ids.map((id) => getJob(companyId, id).catch(() => null)));
      if (cancelled) return;
      const fresh = jobs.filter(Boolean);
      setDocuments((current) =>
        current.map((d) => {
          const job = fresh.find((j) => j.id === d.job?.id);
          return job ? { ...d, job } : d;
        }),
      );
      if (fresh.some((j) => !ACTIVE_JOB.includes(j.status))) {
        await reload();
        notifyKbChanged();
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeJobKey, companyId, reload]);

  const onFile = (event) => {
    const chosen = event.target.files?.[0] ?? null;
    setFile(chosen);
    if (chosen && !title) setTitle(chosen.name.replace(/\.[^.]+$/, ''));
  };

  const upload = async (event) => {
    event.preventDefault();
    if (!file) return;
    setError('');
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('title', title.trim());
      form.append('visibility', visibility);
      if (departmentId !== '') form.append('department_id', departmentId);
      if (effectiveDate !== '') form.append('effective_date', effectiveDate);
      const created = await uploadDocument(companyId, form);
      setDocuments((current) => [{ ...created.document, job: created.job }, ...current]);
      setFile(null);
      setTitle('');
      setDepartmentId('');
      setEffectiveDate('');
      setFormKey((k) => k + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const retry = async (document) => {
    setError('');
    try {
      const job = await retryJob(companyId, document.job.id);
      setDocuments((current) => current.map((d) => (d.id === document.id ? { ...d, status: 'processing', job } : d)));
    } catch (err) {
      setError(err.message);
    }
  };

  const statusLabel = (document) => {
    const job = document.job;
    if (document.status === 'processing' && job) return t(`documents.job.${job.status}`, { defaultValue: job.status });
    return t(`documents.status.${document.status}`, { defaultValue: document.status });
  };
  const departmentName = (id) => departments.find((d) => d.id === id)?.name ?? '';

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('documents.title')}</h1>
      <ErrorAlert message={error} />

      <section className={cardClass}>
        <h2 className="text-lg font-extrabold tracking-tight">{t('documents.uploadTitle')}</h2>
        <form key={formKey} onSubmit={upload} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('documents.file')}</span>
            <input type="file" required accept=".pdf,.docx,.txt,.md" onChange={onFile} className={`${inputClass} mt-1`} />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('documents.docTitle')}</span>
            <input required maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} className={`${inputClass} mt-1`} />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('documents.visibility')}</span>
            <select value={visibility} onChange={(e) => setVisibility(e.target.value)} className={`${inputClass} mt-1`}>
              {VISIBILITIES.map((v) => (
                <option key={v} value={v}>
                  {t(`layers.${v}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('documents.department')}</span>
            <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} className={`${inputClass} mt-1`}>
              <option value="">{t('documents.noDepartment')}</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('documents.effectiveDate')}</span>
            <input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} className={`${inputClass} mt-1`} />
          </label>
          <button type="submit" disabled={busy || !file} className={primaryButton}>
            {busy ? t('documents.uploading') : t('documents.upload')}
          </button>
        </form>
        <p className="mt-3 text-xs text-slate-500">{t('documents.formats')}</p>
      </section>

      {documents.length === 0 ? (
        <EmptyState>{t('documents.empty')}</EmptyState>
      ) : (
        <section className={cardClass}>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-bold uppercase tracking-[0.12em] text-slate-400">
                <th className="py-2 pr-3">{t('documents.colTitle')}</th>
                <th className="py-2 pr-3">{t('documents.colLayer')}</th>
                <th className="py-2 pr-3">{t('documents.colDepartment')}</th>
                <th className="py-2">{t('documents.colStatus')}</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => {
                const job = document.job;
                const running = job && ACTIVE_JOB.includes(job.status);
                const partial = job && job.status !== 'failed' && (job.dropped_items > 0 || job.failed_chunks > 0);
                return (
                  <tr key={document.id} className="border-b border-slate-100 align-top">
                    <td className="py-3 pr-3 font-semibold text-slate-900">{document.title}</td>
                    <td className="py-3 pr-3 text-slate-600">{t(`layers.${document.visibility}`, { defaultValue: document.visibility })}</td>
                    <td className="py-3 pr-3 text-slate-600">{departmentName(document.department_id)}</td>
                    <td className="space-y-2 py-3">
                      <p className="font-semibold text-slate-900">{statusLabel(document)}</p>
                      {running && (
                        <div
                          role="progressbar"
                          aria-label={`${t('documents.progress')} ${document.title}`}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={job.progress}
                          className="h-2 w-48 overflow-hidden rounded-full bg-slate-200"
                        >
                          <div className="h-full bg-blue-600 transition-all" style={{ width: `${job.progress}%` }} />
                        </div>
                      )}
                      {partial && (
                        <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-900">
                          {t('documents.partial', { dropped: job.dropped_items, failed: job.failed_chunks })}
                        </p>
                      )}
                      {job?.status === 'failed' && (
                        <div className="space-y-1">
                          <p className="rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-800">
                            {job.error || t('common.genericError')}
                          </p>
                          <button type="button" onClick={() => retry(document)} className={secondaryButton}>
                            {t('documents.retry')}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

export default DocumentsPage;
