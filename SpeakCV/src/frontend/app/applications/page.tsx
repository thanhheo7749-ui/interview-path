"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { Strings, useLang } from "@/lib/i18n";
import { Application, HiringError, listMyApplications, reuploadCv } from "@/services/hiring";
import { LangToggle } from "@/components/Hiring/SampleNotice";

const POLL_MS = 3000;

function statusText(a: Application, t: Strings): string {
  switch (a.status) {
    case "reading_cv": return t.statusReading;
    case "cv_unreadable": return t.statusUnreadable;
    case "invited": return t.statusInvited;
    case "interview_in_progress": return t.statusInterview;
    case "with_hr": return t.statusWithHr;
    case "decided": return a.decision === "approved" ? t.statusApproved : t.statusRejected;
    case "withdrawn": return t.statusWithdrawn;
    default: return "";
  }
}

function Reupload({ id, onDone }: { id: number; onDone: () => void }) {
  const { t } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await reuploadCv(id, file);
      onDone();
    } catch (err) {
      const status = err instanceof HiringError ? err.status : 0;
      setError(
        status === 413 ? t.tooLarge : status === 415 ? t.unsupportedType : status === 422 ? t.cvTooLong
          : status === 429 ? t.rateLimited : t.genericError,
      );
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div className="mt-2">
      <label className="inline-block cursor-pointer rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-bold text-white">
        {busy ? t.uploading : t.reuploadCv}
        <input ref={input} type="file" accept=".pdf,.docx" onChange={pick} disabled={busy} className="sr-only" />
      </label>
      {error && <p role="alert" className="mt-1 text-sm text-red-400">{error}</p>}
    </div>
  );
}

export default function ApplicationsPage() {
  const { t } = useLang();
  const { user, isLoading } = useAuth();
  const [items, setItems] = useState<Application[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await listMyApplications());
      setError("");
    } catch {
      setError(t.genericError);
    }
  }, [t.genericError]);

  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [user, load]);

  const reading = items?.some((a) => a.status === "reading_cv") ?? false;
  useEffect(() => {
    if (!reading) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [reading, load]);

  if (isLoading) return <main className="min-h-screen bg-theme-secondary p-10 text-theme-muted">{t.loading}</main>;
  if (!user) {
    return (
      <main className="min-h-screen bg-theme-secondary p-10 text-theme-text-secondary">
        <p>{t.loginNeeded}</p>
        <Link href="/login?redirect=%2Fapplications" className="text-blue-400 underline">{t.logIn}</Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-theme-secondary px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-extrabold text-theme-text">{t.appsTitle}</h1>
          <div className="flex items-center gap-3">
            <Link href="/my-data" className="text-sm text-blue-400 underline">{t.myData}</Link>
            <LangToggle />
          </div>
        </div>
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
        {items && items.length === 0 && <p className="text-theme-text-secondary">{t.appsEmpty}</p>}
        <ul className="space-y-3">
          {items?.map((a) => (
            <li key={a.id} className="rounded-2xl border border-theme-border bg-theme-surface p-4">
              <p className="font-bold text-theme-text">{a.job_title}</p>
              <p className="text-sm text-theme-muted">
                {a.company_name}
                {a.is_sample ? ` (${t.sampleTag})` : ""}
              </p>
              <p className="mt-2 text-sm text-theme-text">{statusText(a, t)}</p>
              {a.status === "cv_unreadable" && <Reupload id={a.id} onDone={load} />}
              {a.status === "invited" && (
                <Link href={`/applications/${a.id}/fit`} className="mt-2 inline-block text-sm text-blue-400 underline">
                  {t.seeFit}
                </Link>
              )}
              {a.status === "interview_in_progress" && (
                <Link href={`/applications/${a.id}/screening`} className="mt-2 inline-block text-sm text-blue-400 underline">
                  {t.continueInterview}
                </Link>
              )}
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
