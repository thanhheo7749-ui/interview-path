"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { LEGACY_B2C } from "@/lib/features";
import { format, useLang } from "@/lib/i18n";
import { formatWindowTime, windowState } from "@/lib/interviewWindow";
import { Application, Fit, getApplication, getFit, HiringError, withdrawApplication } from "@/services/hiring";
import AskCompanyWidget from "@/components/Hiring/AskCompanyWidget";
import SampleNotice, { ConfirmDialog, LangToggle } from "@/components/Hiring/SampleNotice";

const FIT_STYLE: Record<string, string> = {
  matches: "bg-emerald-500/20 text-emerald-300",
  partly: "bg-amber-500/20 text-amber-300",
  not_seen: "bg-slate-500/20 text-slate-300",
  not_assessed: "bg-slate-500/20 text-slate-300",
};

export default function FitPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const applicationId = Number(id);
  const { t, lang } = useLang();
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [application, setApplication] = useState<Application | null>(null);
  const [fit, setFit] = useState<Fit | null>(null);
  const [notReady, setNotReady] = useState(false);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState("");
  // Read once per mount: display only, server is the real gate, no need to tick.
  const [now] = useState(() => Date.now());

  useEffect(() => {
    if (!user) return;
    getApplication(applicationId).then(setApplication).catch(() => setError(t.genericError));
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    const load = async () => {
      try {
        const data = await getFit(applicationId);
        if (stopped) return;
        setFit(data);
        setNotReady(false);
      } catch (err) {
        if (stopped) return;
        if (err instanceof HiringError && err.status === 409) {
          setNotReady(true);
          timer = setTimeout(load, 3000);
        } else {
          setError(t.genericError);
        }
      }
    };
    load();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [user, applicationId, t.genericError]);

  const withdraw = async () => {
    setBusy(true);
    setDialogError("");
    try {
      await withdrawApplication(applicationId, reason);
      router.push("/applications");
    } catch {
      setDialogError(t.genericError);
      setBusy(false);
    }
  };

  if (isLoading) return <main className="min-h-screen bg-theme-secondary p-10 text-theme-muted">{t.loading}</main>;
  if (!user) {
    return (
      <main className="min-h-screen bg-theme-secondary p-10 text-theme-text-secondary">
        <p>{t.loginNeeded}</p>
        <Link href={`/login?redirect=${encodeURIComponent(`/applications/${applicationId}/fit`)}`} className="text-blue-400 underline">
          {t.logIn}
        </Link>
      </main>
    );
  }

  const fitWord = (value: string) => (
    value === "matches" ? t.fitMatches : value === "partly" ? t.fitPartly : value === "not_assessed" ? t.fitNotAssessed : t.fitNotSeen
  );

  const win = application?.interview_window ?? null;
  const state = win ? windowState(win, now) : "open";

  return (
    <main className="min-h-screen bg-theme-secondary px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-center justify-between">
          <Link href="/applications" className="text-sm text-blue-400 underline">{t.back}</Link>
          <LangToggle />
        </div>
        {application?.is_sample && <SampleNotice />}
        <header>
          <h1 className="text-2xl font-extrabold text-theme-text">{t.fitTitle}</h1>
          {application && <p className="text-sm text-theme-muted">{application.job_title}, {application.company_name}</p>}
          <p className="mt-2 text-sm text-theme-text-secondary">{t.fitIntro}</p>
        </header>
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
        {notReady && <p role="status" className="text-theme-text-secondary">{t.fitNotReady}</p>}
        {fit && (
          <>
            <ul className="space-y-2">
              {fit.requirements.map((r) => (
                <li key={r.requirement_id} className="flex items-start justify-between gap-3 rounded-xl border border-theme-border bg-theme-surface p-3">
                  <span className="text-sm text-theme-text">{r.text}</span>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${FIT_STYLE[r.fit] ?? FIT_STYLE.not_seen}`}>
                    {fitWord(r.fit)}
                  </span>
                </li>
              ))}
            </ul>
            <section>
              <h2 className="mb-2 text-lg font-bold text-theme-text">{t.teamStyle}</h2>
              {fit.team_style.length === 0 ? (
                <p className="text-sm text-theme-muted">{t.teamStyleEmpty}</p>
              ) : (
                <ul className="space-y-2">
                  {fit.team_style.map((s, i) => (
                    <li key={i} className="rounded-xl border border-theme-border bg-theme-surface p-3">
                      <p className="text-sm font-bold text-theme-text">{s.title}</p>
                      <p className="text-sm text-theme-text-secondary">{s.body}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
        {application && <AskCompanyWidget companySlug={application.company_slug} />}
        {win && (
          <p className="text-sm text-theme-text-secondary">
            {format(t.interviewWindow, {
              start: formatWindowTime(win.start, win.timezone, lang),
              end: formatWindowTime(win.end, win.timezone, lang),
            })}
          </p>
        )}
        {fit && application?.status === "invited" && (
          <div className="flex flex-wrap gap-3">
            {state === "open" ? (
              <>
                {LEGACY_B2C && (
                  <Link
                    href={`/interview?next=${encodeURIComponent(`/applications/${applicationId}/screening`)}`}
                    className="rounded-lg bg-theme-surface px-5 py-2 font-bold text-theme-text"
                  >
                    {t.practiceFirst}
                  </Link>
                )}
                <Link href={`/applications/${applicationId}/screening`} className="rounded-lg bg-blue-600 px-5 py-2 font-bold text-white">
                  {t.startInterview}
                </Link>
              </>
            ) : (
              <button disabled aria-disabled="true" className="rounded-lg bg-theme-surface px-5 py-2 text-theme-muted opacity-50">
                {state === "before" ? t.windowNotOpen : t.windowClosed}
              </button>
            )}
            <button onClick={() => setDialog(true)} className="rounded-lg bg-theme-surface px-5 py-2 text-theme-text">
              {t.withdraw}
            </button>
          </div>
        )}
        {dialog && (
          <ConfirmDialog
            title={t.withdrawTitle}
            body={t.withdrawBody}
            confirmLabel={busy ? t.withdrawing : t.withdraw}
            busy={busy}
            error={dialogError}
            onConfirm={withdraw}
            onCancel={() => setDialog(false)}
          >
            <label className="block text-sm text-theme-text-secondary">
              {t.withdrawReason}
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={2000}
                rows={3}
                className="mt-1 w-full rounded-lg border border-theme-border bg-theme-surface p-2 text-theme-text"
              />
            </label>
          </ConfirmDialog>
        )}
      </div>
    </main>
  );
}
