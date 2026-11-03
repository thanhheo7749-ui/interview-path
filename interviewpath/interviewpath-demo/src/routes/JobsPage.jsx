import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { EmptyState, ErrorAlert, cardClass, primaryButton } from '../components/KbFeedback.jsx';
import { api } from '../lib/api.js';
import { listJobs } from '../lib/jobs.js';

function JobsPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [jobs, setJobs] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    listJobs(companyId)
      .then((data) => {
        if (!cancelled) setJobs(data);
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

  const departmentName = (id) => departments.find((d) => d.id === id)?.name ?? '';

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-extrabold tracking-tight">{t('jobs.title')}</h1>
        <Link to="/jobs/new" className={primaryButton}>
          {t('jobs.new')}
        </Link>
      </div>
      <ErrorAlert message={error} />
      {jobs === null ? (
        !error && <p className="text-sm font-semibold text-slate-500">{t('common.loading')}</p>
      ) : jobs.length === 0 ? (
        <EmptyState>{t('jobs.empty')}</EmptyState>
      ) : (
        <section className={cardClass}>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-bold uppercase tracking-[0.12em] text-slate-400">
                <th className="py-2 pr-3">{t('jobs.colTitle')}</th>
                <th className="py-2 pr-3">{t('jobs.colDepartment')}</th>
                <th className="py-2 pr-3">{t('jobs.colStatus')}</th>
                <th className="py-2 pr-3">{t('jobs.colVersion')}</th>
                <th className="py-2">{t('jobs.colPublished')}</th>
                <th className="py-2 pl-3">{t('jobs.colBoard')}</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b border-slate-100">
                  <td className="py-3 pr-3 font-semibold text-slate-900">
                    <Link to={`/jobs/${job.id}`} className="underline-offset-2 hover:underline">
                      {job.title}
                    </Link>
                  </td>
                  <td className="py-3 pr-3 text-slate-600">{departmentName(job.department_id)}</td>
                  <td className="py-3 pr-3 text-slate-600">{t(`jobs.status.${job.status}`, { defaultValue: job.status })}</td>
                  <td className="py-3 pr-3 text-slate-600">{job.version}</td>
                  <td className="py-3 text-slate-600">{job.published_at ? new Date(job.published_at).toLocaleDateString() : ''}</td>
                  <td className="space-x-3 py-3 pl-3">
                    {job.status !== 'draft' && (
                      <>
                        <Link to={`/jobs/${job.id}/board`} className="font-semibold text-blue-600 underline-offset-2 hover:underline">
                          {t('jobs.openBoard')}
                        </Link>
                        <Link to={`/jobs/${job.id}/channels`} className="font-semibold text-blue-600 underline-offset-2 hover:underline">
                          {t('jobs.insightsChannels')}
                        </Link>
                        <Link to={`/jobs/${job.id}/reality-check`} className="font-semibold text-blue-600 underline-offset-2 hover:underline">
                          {t('jobs.insightsReality')}
                        </Link>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

export default JobsPage;
