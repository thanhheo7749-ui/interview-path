"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { format, useLang } from "@/lib/i18n";
import {
  Application, deleteMyApplication, HiringError, leaveTalentPool, listMyApplications, listMyConsents, listMyTalentEntries, MyConsent,
  TalentEntry, withdrawConsent,
} from "@/services/hiring";
import { ConfirmDialog, LangToggle } from "@/components/Hiring/SampleNotice";

type Pending = { kind: "consent"; id: number; purpose: string } | { kind: "application"; id: number } | { kind: "pool"; id: number } | null;

export default function MyDataPage() {
  const { t, lang } = useLang();
  const { user, isLoading } = useAuth();
  const [apps, setApps] = useState<Application[] | null>(null);
  const [consents, setConsents] = useState<MyConsent[] | null>(null);
  const [pool, setPool] = useState<TalentEntry[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState("");

  const load = useCallback(async () => {
    try {
      setApps(await listMyApplications());
    } catch {
      setError(t.genericError);
    }
    try {
      setConsents(await listMyConsents());
    } catch {
      setError(t.genericError);
    }
    try {
      setPool(await listMyTalentEntries());
    } catch {
      setError(t.genericError);
    }
  }, [t.genericError]);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    setDialogError("");
    try {
      if (pending.kind === "consent") await withdrawConsent(pending.id);
      else if (pending.kind === "pool") await leaveTalentPool(pending.id).catch((err) => {
        // After the application was anonymized the entry has no row left to find: it is already gone.
        if (!(err instanceof HiringError && err.status === 404)) throw err;
      });
      else await deleteMyApplication(pending.id);
      setPending(null);
      await load();
    } catch {
      setDialogError(t.genericError);
    } finally {
      setBusy(false);
    }
  };

  const purposeName = (purpose: string) =>
    ({ cv_processing: t.purposeCv, recording_screening: t.purposeRecording, onboarding_use: t.purposeOnboarding, talent_pool: t.purposePool } as Record<string, string>)[purpose] ?? t.purposeOther;
  // A talent-pool consent is always left as a pool entry is: the kept CV is deleted now, even if the pool list did not load.
  const leavesPool = pending?.kind === "pool" || (pending?.kind === "consent" && pending.purpose === "talent_pool");

  const date = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString(lang === "vi" ? "vi-VN" : "en-GB") : "";

  if (isLoading) return <main className="min-h-screen bg-theme-secondary p-10 text-theme-muted">{t.loading}</main>;
  if (!user) {
    return (
      <main className="min-h-screen bg-theme-secondary p-10 text-theme-text-secondary">
        <p>{t.loginNeeded}</p>
        <Link href="/login?redirect=%2Fmy-data" className="text-blue-400 underline">{t.logIn}</Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-theme-secondary px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-center justify-between">
          <Link href="/applications" className="text-sm text-blue-400 underline">{t.myApplications}</Link>
          <LangToggle />
        </div>
        <header>
          <h1 className="text-2xl font-extrabold text-theme-text">{t.myDataTitle}</h1>
          <p className="text-sm text-theme-text-secondary">{t.myDataIntro}</p>
        </header>
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-theme-text">{t.consentsHeading}</h2>
          {consents && consents.length === 0 && <p className="text-sm text-theme-muted">{t.consentsEmpty}</p>}
          <ul className="space-y-2">
            {consents?.map((c) => {
              const entry = c.purpose === "talent_pool" ? pool.find((e) => e.consent_id === c.id) : undefined;
              return (
              <li key={c.id} className="rounded-xl border border-theme-border bg-theme-surface p-3">
                <p className="text-sm font-bold text-theme-text">{purposeName(c.purpose)}{c.job_title ? `: ${c.job_title}` : ""}</p>
                <p className="text-xs text-theme-muted">
                  {format(t.consentGranted, { date: date(c.granted_at) })}
                  {c.withdrawn_at ? `. ${format(t.consentWithdrawnOn, { date: date(c.withdrawn_at) })}` : ""}
                </p>
                {entry && (
                  <p className="text-xs text-theme-text-secondary" data-testid={`pool-status-${entry.status}`}>
                    {entry.status === "active" ? format(t.poolActive, { date: date(entry.expires_at) }) : entry.status === "expired" ? t.poolExpired : t.poolLeft}
                  </p>
                )}
                {!c.withdrawn_at && (entry ? entry.status === "active" : true) && (
                  <button
                    onClick={() => setPending(entry ? { kind: "pool", id: entry.id } : { kind: "consent", id: c.id, purpose: c.purpose })}
                    className="mt-2 text-sm text-red-400 underline"
                  >
                    {c.purpose === "talent_pool" ? t.leavePool : t.withdrawConsent}
                  </button>
                )}
              </li>
              );
            })}
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-theme-text">{t.applicationsHeading}</h2>
          {apps && apps.length === 0 && <p className="text-sm text-theme-muted">{t.appsEmpty}</p>}
          <ul className="space-y-2">
            {apps?.map((a) => (
              <li key={a.id} className="rounded-xl border border-theme-border bg-theme-surface p-3">
                <p className="text-sm font-bold text-theme-text">{a.job_title}</p>
                <p className="text-xs text-theme-muted">{a.company_name}</p>
                <button onClick={() => setPending({ kind: "application", id: a.id })} className="mt-2 text-sm text-red-400 underline">
                  {t.deleteApplication}
                </button>
              </li>
            ))}
          </ul>
        </section>

        {pending && (
          <ConfirmDialog
            title={pending.kind === "application" ? t.deleteTitle : leavesPool ? t.leavePoolTitle : t.withdrawConsentTitle}
            body={
              pending.kind === "application" ? t.deleteBody
                : leavesPool ? t.leavePoolBody
                : pending.purpose === "recording_screening" ? t.withdrawRecordingBody
                : pending.purpose === "onboarding_use" ? t.withdrawOnboardingBody
                : t.withdrawCvBody
            }
            confirmLabel={
              busy ? (pending.kind === "application" ? t.deleting : leavesPool ? t.leaving : t.sending)
                : pending.kind === "application" ? t.deleteApplication : leavesPool ? t.leavePool : t.withdrawConsent
            }
            busy={busy}
            error={dialogError}
            onConfirm={confirm}
            onCancel={() => setPending(null)}
          />
        )}
      </div>
    </main>
  );
}
