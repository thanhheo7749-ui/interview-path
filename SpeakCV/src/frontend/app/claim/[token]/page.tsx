"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format, useLang } from "@/lib/i18n";
import { claimApplication, ClaimInfo, ConsentText, getClaimInfo, getConsentText } from "@/services/hiring";
import { LangToggle } from "@/components/Hiring/SampleNotice";

export default function ClaimPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const { t, lang } = useLang();
  const router = useRouter();
  const [info, setInfo] = useState<ClaimInfo | null>(null);
  const [consent, setConsent] = useState<ConsentText | null>(null);
  const [agreed, setAgreed] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getClaimInfo(token)
      .then(setInfo)
      .catch(() => setError(t.genericError));
    getConsentText("cv_processing", lang)
      .then(setConsent)
      .catch(() => {});
  }, [token, lang, t.genericError]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!info || !agreed) return;
    setBusy(true);
    setError("");
    try {
      const res = await claimApplication(token, consent?.version ?? info.consent_version, consent?.language ?? lang);
      sessionStorage.setItem("token", res.access_token);
      sessionStorage.setItem("userName", info.candidate_name || res.email);
      sessionStorage.setItem("userRole", "user");
      window.dispatchEvent(new Event("auth-changed"));
      router.push(`/applications/${res.application_id}/fit`);
    } catch {
      setError(t.genericError);
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-theme-secondary px-4 py-10">
      <div className="mx-auto max-w-xl space-y-4">
        <div className="flex justify-end">
          <LangToggle />
        </div>
        {!info ? (
          <p className="text-theme-muted">{error || t.loading}</p>
        ) : (
          <form onSubmit={submit} className="rounded-2xl border border-theme-border bg-theme-surface p-6 space-y-4">
            <h1 className="text-xl font-extrabold text-theme-text">{t.claimTitle}</h1>
            <p className="text-sm text-theme-text-secondary">
              {format(t.claimBody, { job: info.job_title, company: info.company_name })}
            </p>
            {consent && (
              <div className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-theme-secondary p-3 text-xs text-theme-text-secondary">
                {consent.text}
              </div>
            )}
            <label className="flex items-start gap-2 text-sm text-theme-text">
              <input type="checkbox" required checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1" />
              {t.consentAgree}
            </label>
            {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
            <button
              type="submit"
              disabled={busy || !agreed}
              className="px-5 py-2.5 rounded-lg bg-blue-600 text-white font-bold disabled:opacity-50"
            >
              {busy ? t.sending : t.claimSubmit}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
