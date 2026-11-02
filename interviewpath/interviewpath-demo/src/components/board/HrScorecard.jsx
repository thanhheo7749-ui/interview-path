import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getScorecard } from '../../lib/bridges.js';
import { ErrorAlert } from '../KbFeedback.jsx';

// What the hiring manager submitted, read-only. It is advice to HR: nothing here decides or moves a candidate.
function HrScorecard({ companyId, appId }) {
  const { t, i18n } = useTranslation();
  const [card, setCard] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getScorecard(companyId, appId)
      .then((row) => { if (!cancelled) { setCard(row); setLoaded(true); } })
      .catch((err) => { if (!cancelled) { setError(err.message); setLoaded(true); } });
    return () => { cancelled = true; };
  }, [companyId, appId]);

  const submitted = card?.submitted_at
    ? new Date(card.submitted_at).toLocaleDateString(i18n.language, { dateStyle: 'medium' })
    : '';

  return (
    <section aria-labelledby="hr-scorecard-title" data-testid="hr-scorecard" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h3 id="hr-scorecard-title" className="text-sm font-extrabold text-slate-950">{t('bridges.scorecard.hrView.title')}</h3>
      <p className="text-xs text-slate-500">{t('bridges.scorecard.hrView.hint')}</p>
      <ErrorAlert message={error} />
      {!loaded && <p className="text-xs text-slate-500">{t('common.loading')}</p>}
      {loaded && !card && !error && <p data-testid="scorecard-none" className="text-sm text-slate-600">{t('bridges.scorecard.hrView.none')}</p>}
      {card && (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-500">{t('bridges.scorecard.hrView.by', { name: card.manager_name, date: submitted })}</p>
          <p className="text-sm text-slate-800">
            <span className="font-bold">{t('bridges.scorecard.hrView.recommendation')}: </span>
            <span data-testid="scorecard-recommendation" className="font-extrabold text-slate-950">{t(`bridges.scorecard.hrView.${card.recommendation}`)}</span>
          </p>
          <div>
            <h4 className="text-xs font-bold text-slate-600">{t('bridges.scorecard.hrView.scores')}</h4>
            <ul className="mt-1 space-y-1">
              {card.requirement_scores.map((s) => (
                <li key={s.requirement_id} className="flex justify-between gap-3 rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
                  <span className="text-slate-800">{s.text}</span>
                  <span className="font-bold text-slate-950">{t('bridges.scorecard.hrView.score', { score: s.score })}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-600">{t('bridges.scorecard.hrView.notes')}</h4>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{card.notes || t('bridges.scorecard.hrView.noNotes')}</p>
          </div>
        </div>
      )}
    </section>
  );
}

export default HrScorecard;
