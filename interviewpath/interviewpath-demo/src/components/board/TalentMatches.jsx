import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getTalentMatches, inviteFromPool } from '../../lib/posthire.js';
import { ErrorAlert, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// People who agreed to stay in the talent pool. Aliases only. Viewing calls the AI, so it waits for the button.
function TalentMatches({ companyId, jobId, onInvited }) {
  const { t } = useTranslation();
  const [matches, setMatches] = useState(null);
  const [invited, setInvited] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const find = async () => {
    setBusy(true);
    setError('');
    try {
      setMatches(await getTalentMatches(companyId, jobId));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const invite = async (match) => {
    setBusy(true);
    setError('');
    try {
      const application = await inviteFromPool(companyId, match.entry_id, Number(jobId));
      setInvited((current) => ({ ...current, [match.entry_id]: application.alias }));
      await onInvited();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="talent-title" data-testid="talent-matches" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 id="talent-title" className="text-base font-extrabold text-slate-950">{t('posthire.talent.title')}</h2>
      <p className="text-xs text-slate-600">{t('posthire.talent.intro')}</p>
      <ErrorAlert message={error} />
      <button type="button" disabled={busy} onClick={find} className={secondaryButton}>
        {busy && !matches ? t('common.loading') : t('posthire.talent.find')}
      </button>
      {matches && matches.length === 0 && <p className="text-sm text-slate-500">{t('posthire.talent.none')}</p>}
      {matches && matches.length > 0 && (
        <ul className="space-y-2">
          {matches.map((match) => (
            <li key={match.entry_id} data-testid={`match-${match.alias}`} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3">
              <div>
                <p className="text-sm font-extrabold text-slate-950">{match.alias}</p>
                <p className="text-xs text-slate-600">
                  {t(`posthire.talent.strength.${match.strength}`, { defaultValue: match.strength })}
                  {match.must_haves_total > 0 && ` · ${t('posthire.talent.mustHaves', { met: match.must_haves_met, total: match.must_haves_total })}`}
                </p>
              </div>
              {invited[match.entry_id] ? (
                <span className="text-xs font-bold text-emerald-700">{t('posthire.talent.invited', { alias: invited[match.entry_id] })}</span>
              ) : (
                <button type="button" disabled={busy} onClick={() => invite(match)} className={primaryButton}>{t('posthire.talent.invite')}</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default TalentMatches;
