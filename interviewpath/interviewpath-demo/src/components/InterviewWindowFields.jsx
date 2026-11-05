import { useTranslation } from 'react-i18next';
import { inputClass } from './KbFeedback.jsx';

// `datetime-local` has no offset. Converting through `Date` local getters/setters keeps the
// instant correct across DST without manual offset math (shortcut: HR sees times in their own
// browser tz even if it differs from the stored display tz; the saved instant is unaffected).
export const isoToLocalInput = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export const localInputToIso = (value) => {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
};

export default function InterviewWindowFields({ enabled, start, end, readOnly, onEnabled, onStart, onEnd }) {
  const { t } = useTranslation();
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <fieldset>
      <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
        <input type="checkbox" checked={enabled} disabled={readOnly} onChange={(e) => onEnabled(e.target.checked)} />
        {t('jobs.schedulingEnabled')}
      </label>
      {enabled && (
        <div className="mt-2 flex flex-wrap gap-3">
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('jobs.windowStart')}</span>
            <input
              type="datetime-local"
              value={start}
              disabled={readOnly}
              onChange={(e) => onStart(e.target.value)}
              className={`${inputClass} mt-1`}
            />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            <span className="block">{t('jobs.windowEnd')}</span>
            <input
              type="datetime-local"
              value={end}
              disabled={readOnly}
              onChange={(e) => onEnd(e.target.value)}
              className={`${inputClass} mt-1`}
            />
          </label>
          <p className="w-full text-xs text-slate-500">{t('jobs.windowTimezoneHint', { tz: timezone })}</p>
        </div>
      )}
    </fieldset>
  );
}
