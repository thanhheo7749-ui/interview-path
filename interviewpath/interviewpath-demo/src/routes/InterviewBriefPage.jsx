import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import BriefEditor from '../components/board/BriefEditor.jsx';
import { ErrorAlert, cardClass, inputClass, primaryButton } from '../components/KbFeedback.jsx';
import { getMyInterview, submitScorecard } from '../lib/bridges.js';

const SCORES = [1, 2, 3, 4, 5];

// One row per requirement, a recommendation and notes. The manager decides; HR makes the final call.
function ScorecardForm({ companyId, appId, requirements, existing, onSaved }) {
  const { t } = useTranslation();
  const [scores, setScores] = useState(() => Object.fromEntries((existing?.requirement_scores ?? []).map((s) => [s.requirement_id, String(s.score)])));
  const [recommendation, setRecommendation] = useState(existing?.recommendation ?? '');
  const [notes, setNotes] = useState(existing?.notes ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const complete = requirements.every((r) => scores[r.id]) && recommendation !== '';

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const saved = await submitScorecard(companyId, appId, {
        scores: requirements.map((r) => ({ requirement_id: r.id, score: Number(scores[r.id]) })),
        recommendation,
        notes,
      });
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} data-testid="scorecard-form" className={`${cardClass} space-y-4`}>
      <h2 className="text-lg font-bold">{t('bridges.scorecard.title')}</h2>
      <p className="text-sm text-slate-600">{t('bridges.scorecard.hint')}</p>
      {existing?.submitted_at && <p data-testid="scorecard-submitted" className="text-sm font-bold text-slate-900">{t('bridges.scorecard.submitted')}</p>}
      <ErrorAlert message={error} />
      <ul className="space-y-3">
        {requirements.map((req) => (
          <li key={req.id} className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm font-semibold text-slate-900">{req.text}</span>
            <select
              aria-label={t('bridges.scorecard.scoreFor', { requirement: req.text })}
              value={scores[req.id] ?? ''}
              onChange={(e) => setScores({ ...scores, [req.id]: e.target.value })}
              className={inputClass}
            >
              <option value="">{t('bridges.scorecard.choose')}</option>
              {SCORES.map((n) => <option key={n} value={n}>{t(`bridges.scorecard.scale.${n}`)}</option>)}
            </select>
          </li>
        ))}
      </ul>
      <fieldset className="space-y-1">
        <legend className="text-sm font-bold text-slate-800">{t('bridges.scorecard.recommendation')}</legend>
        {['hire', 'no_hire'].map((value) => (
          <label key={value} className="mr-4 inline-flex items-center gap-2 text-sm font-semibold text-slate-800">
            <input type="radio" name="recommendation" value={value} checked={recommendation === value} onChange={() => setRecommendation(value)} />
            {t(`bridges.scorecard.${value}`)}
          </label>
        ))}
      </fieldset>
      <label className="block text-sm font-bold text-slate-800">
        {t('bridges.scorecard.notes')}
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} maxLength={5000} className={`${inputClass} mt-1 w-full`} />
      </label>
      <button type="submit" disabled={busy || !complete} className={primaryButton}>
        {existing?.submitted_at ? t('bridges.scorecard.resubmit') : t('bridges.scorecard.submit')}
      </button>
    </form>
  );
}

// The manager's reading view of a sent brief, with the candidate's identity (HR approved it) and the scorecard.
function InterviewBriefPage() {
  const { t } = useTranslation();
  const { appId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getMyInterview(companyId, appId)
      .then((data) => { if (!cancelled) setDetail(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, appId]);

  return (
    <div className="max-w-4xl space-y-6 p-8">
      <Link to="/my-interviews" className="text-sm font-bold text-blue-700 hover:underline">{t('bridges.interviews.back')}</Link>
      <ErrorAlert message={error} />
      {detail && (
        <>
          <header className="space-y-1">
            <h1 className="text-2xl font-extrabold tracking-tight">{detail.job.title}</h1>
            <p data-testid="candidate-identity" className="text-sm font-semibold text-slate-800">
              {detail.candidate.name} ({detail.candidate.email}) · {detail.alias}
            </p>
            <p className="text-xs text-slate-500">{t('bridges.interviews.identityLogged')}</p>
          </header>
          <section className={`${cardClass} space-y-3`} data-testid="manager-brief">
            <h2 className="text-lg font-bold">{t('bridges.brief.title')}</h2>
            <p className="text-xs text-slate-500">{t('bridges.interviews.briefHint')}</p>
            <BriefEditor content={detail.brief.content} />
            <p className="text-xs text-slate-500">{t('bridges.interviews.recordingHeld')}</p>
          </section>
          <ScorecardForm
            key={detail.scorecard?.submitted_at ?? 'new'}
            companyId={companyId}
            appId={appId}
            requirements={detail.requirements}
            existing={detail.scorecard}
            onSaved={(scorecard) => setDetail({ ...detail, scorecard })}
          />
        </>
      )}
      {!detail && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
    </div>
  );
}

export default InterviewBriefPage;
