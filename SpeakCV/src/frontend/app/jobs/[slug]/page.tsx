"use client";

import { Suspense, use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { safeRedirect } from "@/lib/safeRedirect";
import { format, Strings, useLang } from "@/lib/i18n";
import { applyToJob, ConsentText, getConsentText, getPublicJob, HiringError, PublicJob } from "@/services/hiring";
import SampleNotice, { LangToggle } from "@/components/Hiring/SampleNotice";

const MAX_CV_BYTES = 20 * 1024 * 1024; // the server's default limit; the server still has the final say
const CV_NAME = /\.(pdf|docx)$/i;

function applyErrorText(err: unknown, t: Strings, lang: string): string {
  if (!(err instanceof HiringError)) return t.genericError;
  const detail = err.detail as { message?: string; reapply_after?: string } | string | null;
  switch (err.status) {
    case 409:
      if (detail && typeof detail === "object" && detail.reapply_after) {
        const date = new Date(detail.reapply_after).toLocaleDateString(lang === "vi" ? "vi-VN" : "en-GB");
        return `${t.alreadyApplied} ${format(t.reapplyAfter, { date })}`;
      }
      if (detail && typeof detail === "object" && detail.message) return t.consentChanged;
      return typeof detail === "string" ? detail : t.genericError;
    case 413:
      return t.tooLarge;
    case 415:
      return t.unsupportedType;
    case 422:
      return t.cvTooLong;
    case 429:
      return t.rateLimited;
    default:
      return t.genericError;
  }
}

function ApplyForm({ job, src }: { job: PublicJob; src: string | null }) {
  const { t, lang } = useLang();
  const router = useRouter();
  const [consent, setConsent] = useState<ConsentText | null>(null);
  const [consentError, setConsentError] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getConsentText("cv_processing", lang)
      .then((c) => !cancelled && (setConsent(c), setConsentError(false)))
      .catch(() => !cancelled && setConsentError(true));
    return () => {
      cancelled = true;
    };
  }, [lang]);

  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0] ?? null;
    setError("");
    if (chosen && !CV_NAME.test(chosen.name)) {
      setFile(null);
      setError(t.cvWrongType);
      e.target.value = "";
    } else if (chosen && chosen.size > MAX_CV_BYTES) {
      setFile(null);
      setError(t.cvTooBig);
      e.target.value = "";
    } else {
      setFile(chosen);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return setError(t.cvRequired);
    if (!consent || !agreed) return;
    setBusy(true);
    setError("");
    try {
      await applyToJob(job.slug, file, consent.version, src);
      router.push("/applications");
    } catch (err) {
      setError(applyErrorText(err, t, lang));
      if (err instanceof HiringError && err.status === 409 && typeof err.detail === "object") {
        setAgreed(false);
        getConsentText("cv_processing", lang).then(setConsent).catch(() => {});
      }
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="rounded-2xl border border-theme-border bg-theme-surface p-5 space-y-4">
      <h2 className="text-lg font-bold text-theme-text">{t.applyTitle}</h2>
      <label className="block text-sm text-theme-text-secondary">
        {t.cvFile}
        <input
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={pick}
          className="mt-1 block w-full text-theme-text"
        />
      </label>
      <div>
        <h3 className="text-sm font-bold text-theme-text">{t.consentHeading}</h3>
        {consent ? (
          <div className="mt-1 max-h-60 overflow-y-auto whitespace-pre-wrap rounded-lg bg-theme-secondary p-3 text-sm text-theme-text-secondary">
            {consent.text}
          </div>
        ) : consentError ? (
          <p role="alert" className="text-sm text-red-400">{t.consentLoadError}</p>
        ) : (
          <p className="text-sm text-theme-muted">{t.loading}</p>
        )}
      </div>
      <label className="flex items-start gap-2 text-sm text-theme-text">
        <input type="checkbox" required checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1" />
        {t.consentAgree}
      </label>
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={busy || !consent || !agreed || !file}
        className="px-5 py-2 rounded-lg bg-blue-600 text-white font-bold disabled:opacity-50"
      >
        {busy ? t.sending : t.submitApplication}
      </button>
    </form>
  );
}

function JobView({ slug }: { slug: string }) {
  const { t } = useLang();
  const { user, isLoading } = useAuth();
  const src = useSearchParams().get("src");
  const [job, setJob] = useState<PublicJob | null>(null);
  const [missing, setMissing] = useState(false);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    getPublicJob(slug, src)
      .then(setJob)
      .catch(() => setMissing(true));
  }, [slug, src]);

  const loginHref = () => {
    const back = safeRedirect(window.location.pathname + window.location.search, "/");
    return `/login?redirect=${encodeURIComponent(back)}`;
  };

  if (missing) return <p className="text-theme-text-secondary">{t.jobNotFound}</p>;
  if (!job) return <p className="text-theme-muted">{t.loading}</p>;

  return (
    <div className="space-y-6">
      {job.is_sample && <SampleNotice />}
      <header>
        <p className="text-sm text-theme-muted">{job.company_name}</p>
        <h1 className="text-3xl font-extrabold text-theme-text">{job.title}</h1>
      </header>
      <p className="whitespace-pre-wrap text-theme-text-secondary">{job.description}</p>
      {job.requirements.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-theme-text mb-2">{t.requirements}</h2>
          <ul className="space-y-1">
            {job.requirements.map((r, i) => (
              <li key={i} className="text-sm text-theme-text-secondary">
                {r.text}{" "}
                <span className="text-xs text-theme-muted">({r.must_have ? t.mustHave : t.niceToHave})</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!job.can_apply ? (
        <p className="text-theme-text-secondary">{t.jobClosed}</p>
      ) : isLoading ? null : !user ? (
        <Link href={loginHref()} className="inline-block px-5 py-2 rounded-lg bg-blue-600 text-white font-bold">
          {t.loginToApply}
        </Link>
      ) : showForm ? (
        <ApplyForm job={job} src={src} />
      ) : (
        <button onClick={() => setShowForm(true)} className="px-5 py-2 rounded-lg bg-blue-600 text-white font-bold">
          {t.apply}
        </button>
      )}
    </div>
  );
}

export default function JobPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  return (
    <main className="min-h-screen bg-theme-secondary px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="flex justify-end">
          <LangToggle />
        </div>
        <Suspense fallback={null}>
          <JobView slug={slug} />
        </Suspense>
      </div>
    </main>
  );
}
