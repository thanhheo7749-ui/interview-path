"use client";

import { useLang } from "@/lib/i18n";

/** Hidden for this deployment's demo walkthroughs. is_sample stays true server-side (gates simulate-hiring etc.). */
export default function SampleNotice() {
  return null;
}

/** Small English/Vietnamese switch. The choice is kept in localStorage. */
export function LangToggle() {
  const { lang, setLang, t } = useLang();
  return (
    <div className="flex items-center gap-1 text-xs" role="group" aria-label={t.language}>
      {(["en", "vi"] as const).map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLang(code)}
          aria-pressed={lang === code}
          className={`px-2 py-1 rounded-md font-bold uppercase ${
            lang === code ? "bg-blue-600 text-white" : "bg-theme-surface text-theme-text-secondary"
          }`}
        >
          {code}
        </button>
      ))}
    </div>
  );
}

/** A modal dialog for confirming an action. Children hold any extra fields. */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  busy,
  error,
  onConfirm,
  onCancel,
  children,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  busy: boolean;
  error?: string;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
}) {
  const { t } = useLang();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-md rounded-2xl bg-theme-secondary border border-theme-border p-6 space-y-4">
        <h2 className="text-lg font-bold text-theme-text">{title}</h2>
        <p className="text-sm text-theme-text-secondary">{body}</p>
        {children}
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onCancel} disabled={busy} className="px-4 py-2 rounded-lg bg-theme-surface text-theme-text">
            {t.cancel}
          </button>
          <button type="button" onClick={onConfirm} disabled={busy} className="px-4 py-2 rounded-lg bg-red-600 text-white font-bold disabled:opacity-50">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
