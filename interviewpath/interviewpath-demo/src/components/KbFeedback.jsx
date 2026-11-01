import { useTranslation } from 'react-i18next';

export const inputClass =
  'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:border-blue-500';
export const primaryButton =
  'rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-card transition hover:bg-blue-700 disabled:opacity-60';
export const secondaryButton =
  'rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-800 shadow-card transition hover:bg-slate-50 disabled:opacity-60';
export const cardClass = 'rounded-2xl border border-slate-200 bg-white p-6 shadow-card';

export function ErrorAlert({ message }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
      {message}
    </p>
  );
}

// `warnings` is optional in API responses, so anything that is not a non-empty list renders nothing.
export function WarningList({ warnings, onDismiss }) {
  const { t } = useTranslation();
  if (!Array.isArray(warnings) || warnings.length === 0) return null;
  return (
    <div className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <p className="font-bold">{t('kb.warningsTitle')}</p>
      <ul className="list-disc pl-5">
        {warnings.map((warning) => (
          <li key={String(warning)}>{String(warning)}</li>
        ))}
      </ul>
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="text-xs font-bold underline">
          {t('common.dismiss')}
        </button>
      )}
    </div>
  );
}

export function EmptyState({ children }) {
  return <p className={`${cardClass} text-sm font-semibold text-slate-600`}>{children}</p>;
}

// An inline confirmation for an action that changes what the company knowledge says.
export function ConfirmBar({ message, confirmLabel, busy, onConfirm, onCancel }) {
  const { t } = useTranslation();
  return (
    <div role="alertdialog" aria-label={message} className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <p className="font-semibold">{message}</p>
      <div className="flex gap-2">
        <button type="button" disabled={busy} onClick={onConfirm} className={primaryButton}>
          {confirmLabel}
        </button>
        <button type="button" disabled={busy} onClick={onCancel} className={secondaryButton}>
          {t('common.cancel')}
        </button>
      </div>
    </div>
  );
}
