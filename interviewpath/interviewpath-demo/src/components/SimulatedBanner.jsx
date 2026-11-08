import { useTranslation } from 'react-i18next';

// Rendered whenever a response says `simulated`. It has no close button on purpose.
export function SimulatedBanner() {
  const { t } = useTranslation();
  return (
    <div role="status" data-testid="simulated-banner" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <p className="font-extrabold uppercase tracking-[0.12em]">{t('insights.simulated')}</p>
      <p className="mt-1">{t('insights.simulatedNote')}</p>
    </div>
  );
}

// Shown only when a job has both real and simulated rows. The two are never blended.
export function DataToggle({ simulated, onChange }) {
  const { t } = useTranslation();
  const button = (wantSimulated, label) => (
    <button
      type="button"
      aria-pressed={simulated === wantSimulated}
      onClick={() => onChange(wantSimulated ? 'simulated' : 'real')}
      className={`px-4 py-2 text-sm font-bold ${simulated === wantSimulated ? 'bg-blue-600 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
    >
      {label}
    </button>
  );
  return (
    <div role="group" aria-label={t('insights.dataToggle')} className="inline-flex overflow-hidden rounded-xl border border-slate-200 shadow-card">
      {button(false, t('insights.real'))}
      {button(true, t('insights.simulatedShort'))}
    </div>
  );
}
