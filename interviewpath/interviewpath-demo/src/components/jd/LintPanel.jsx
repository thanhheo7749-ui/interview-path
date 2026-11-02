import { useTranslation } from 'react-i18next';
import { secondaryButton } from '../KbFeedback.jsx';

// The lint result of the draft: what blocks publishing and what only warns. HR can mark a conflicting line as a
// different scope, run the checks again, or acknowledge a check that could not run.
function LintPanel({ issues, lineNumbers, canAct, busy, onDifferentScope, onRerun, onAcknowledge }) {
  const { t } = useTranslation();
  const blocking = issues.filter((issue) => issue.severity === 'block');

  return (
    <section aria-label={t('jd.lint.title')} data-testid="lint-panel" data-blocking={blocking.length} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-extrabold tracking-tight">{t('jd.lint.title')}</h2>
        {canAct && (
          <button type="button" disabled={busy} onClick={onRerun} className={secondaryButton}>
            {t('jd.lint.rerun')}
          </button>
        )}
      </div>
      {issues.length === 0 && (
        <p data-testid="lint-clear" className="text-sm font-semibold text-emerald-800">
          {t('jd.lint.clear')}
        </p>
      )}
      <ul className="space-y-2">
        {issues.map((issue, index) => {
          const isBlock = issue.severity === 'block';
          const nodeId = issue.check === 'conflict' ? issue.node_id ?? null : null;
          return (
            <li
              key={`${issue.check}-${issue.line_id}-${index}`}
              data-testid={isBlock ? 'lint-block' : 'lint-warning'}
              className={`space-y-2 rounded-xl border px-3 py-2 text-sm ${isBlock ? 'border-red-200 bg-red-50 text-red-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}
            >
              <p>
                <span className="mr-2 font-bold">{isBlock ? t('jd.lint.blocking') : t('jd.lint.warning')}</span>
                <span className="font-semibold">{t(`jd.lint.checks.${issue.check}`, { defaultValue: issue.check })}</span>
                {issue.line_id && lineNumbers[issue.line_id] ? ` (${t('jd.lint.line', { number: lineNumbers[issue.line_id] })})` : ''}
              </p>
              <p>{issue.message}</p>
              {issue.check === 'conflict' && issue.node_title && (
                <p data-testid="lint-fact" className="font-semibold">
                  {t('jd.lint.fact', { title: issue.node_title })}
                </p>
              )}
              {canAct && issue.check === 'conflict' && nodeId != null && (
                <button type="button" disabled={busy} onClick={() => onDifferentScope(issue.line_id, nodeId)} className={secondaryButton}>
                  {t('jd.lint.differentScope')}
                </button>
              )}
              {canAct && issue.check === 'unchecked' && isBlock && (
                <button type="button" disabled={busy} onClick={() => onAcknowledge(issue.line_id)} className={secondaryButton}>
                  {t('jd.lint.acknowledge')}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default LintPanel;
