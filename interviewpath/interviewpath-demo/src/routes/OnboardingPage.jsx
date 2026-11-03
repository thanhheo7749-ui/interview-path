import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import ProbationControl from '../components/board/ProbationControl.jsx';
import { ConfirmBar, ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import { useCompany } from '../company/CompanyContext.jsx';
import { approveOnboarding, editOnboarding, getOnboarding } from '../lib/posthire.js';

const PHASES = [30, 60, 90];

// HR and the department's manager read, edit and approve the 30-60-90 plan. The hire sees it only after approval.
// Nobody here sees which items the hire has ticked: the plan is not a way to watch an employee.
function OnboardingPage() {
  const { t } = useTranslation();
  const { planId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [plan, setPlan] = useState(null);
  const [edits, setEdits] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getOnboarding(companyId, planId)
      .then((data) => { if (!cancelled) setPlan(data); })
      .catch((err) => { if (!cancelled) setError(err.status === 404 ? t('onboarding.plan.notFound') : err.message); });
    return () => { cancelled = true; };
  }, [companyId, planId, t]);

  const draft = plan?.status === 'draft';
  const change = (id, patch) => setEdits((previous) => ({ ...previous, [id]: { ...previous[id], ...patch } }));
  const dirty = Object.keys(edits).length > 0;
  const shown = (item) => ({ ...item, ...edits[item.id] });

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
      setConfirming(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const save = () => run(async () => {
    setPlan(await editOnboarding(companyId, plan.id, Object.entries(edits).map(([id, edit]) => ({ id: Number(id), ...edit }))));
    setEdits({});
  });
  const approve = () => run(async () => setPlan(await approveOnboarding(companyId, plan.id)));

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('onboarding.plan.title')}</h1>
      <ErrorAlert message={error} />
      {!plan && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {plan && (
        <>
          <p className="text-sm font-semibold text-slate-700">
            {plan.alias} · {plan.job_title} ·{' '}
            <span data-testid="plan-status">{t(`onboarding.plan.status.${plan.status}`, { defaultValue: plan.status })}</span>
          </p>
          <p className="text-xs text-slate-500">
            {plan.used_interview_data ? t('onboarding.plan.usedInterview') : t('onboarding.plan.teamKnowledgeOnly')}
          </p>
          <div className="grid gap-4 lg:grid-cols-3">
            {PHASES.map((phase) => (
              <section key={phase} data-testid={`phase-${phase}`} aria-label={t('onboarding.plan.phase', { days: phase })} className={`${cardClass} space-y-3`}>
                <h2 className="text-sm font-extrabold">{t('onboarding.plan.phase', { days: phase })}</h2>
                <ul className="space-y-3">
                  {plan.items.map(shown).filter((item) => item.phase === phase && !item.remove).map((item) => (
                    <li key={item.id} data-testid="plan-item" className="space-y-1 rounded-xl border border-slate-200 p-3">
                      {draft ? (
                        <>
                          <input
                            aria-label={t('onboarding.plan.itemTitle')}
                            value={item.title}
                            maxLength={300}
                            onChange={(e) => change(item.id, { title: e.target.value })}
                            className={`${inputClass} w-full`}
                          />
                          <div className="flex items-center gap-2">
                            <select
                              aria-label={t('onboarding.plan.movePhase')}
                              value={item.phase}
                              onChange={(e) => change(item.id, { phase: Number(e.target.value) })}
                              className={inputClass}
                            >
                              {PHASES.map((days) => <option key={days} value={days}>{t('onboarding.plan.phase', { days })}</option>)}
                            </select>
                            <button type="button" onClick={() => change(item.id, { remove: true })} className="text-xs font-bold text-red-700 underline">
                              {t('onboarding.plan.remove')}
                            </button>
                          </div>
                        </>
                      ) : (
                        <p className="text-sm font-semibold">{item.title}</p>
                      )}
                      <p data-testid="item-source" className="text-xs text-slate-500">
                        {item.learning_resource
                          ? <>{t('onboarding.plan.fromResource')}: <a href={item.learning_resource.url} target="_blank" rel="noopener noreferrer" className="underline">{item.learning_resource.title}</a></>
                          : `${t('onboarding.plan.fromKnowledge')}: ${item.source_title ?? t('onboarding.plan.sourceHidden')}`}
                      </p>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          {draft && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy || !dirty} onClick={save} className={secondaryButton}>{t('onboarding.plan.save')}</button>
                <button type="button" disabled={busy || dirty} onClick={() => setConfirming(true)} className={primaryButton}>{t('onboarding.plan.approve')}</button>
              </div>
              {dirty && <p className="text-xs text-slate-500">{t('onboarding.plan.saveFirst')}</p>}
              {confirming && (
                <ConfirmBar
                  message={t('onboarding.plan.approveConfirm')}
                  confirmLabel={t('onboarding.plan.approveYes')}
                  busy={busy}
                  onConfirm={approve}
                  onCancel={() => setConfirming(false)}
                />
              )}
            </div>
          )}
          <ProbationControl companyId={companyId} appId={plan.application_id} initial={plan.probation_result} />
        </>
      )}
    </div>
  );
}

export default OnboardingPage;
