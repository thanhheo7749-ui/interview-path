"use client";

import { useEffect, useState } from "react";
import { format, useLang } from "@/lib/i18n";
import {
  Application, ConsentText, getConsentText, getOnboardingConsent, grantOnboardingConsent, HiringError, joinTalentPool,
  OnboardingConsent, TalentEntry,
} from "@/services/hiring";

const declinedKey = (id: number) => `speakcv_onboarding_declined_${id}`;

/** HR's sent message and the catalogue links it carries, and the day the job takes a new application. Nothing else. */
export function FeedbackBlock({ app }: { app: Application }) {
  const { t, lang } = useLang();
  const reapply = app.reapply_after ? new Date(app.reapply_after).toLocaleDateString(lang === "vi" ? "vi-VN" : "en-GB") : null;
  const feedback = app.feedback;
  return (
    <div className="mt-3 space-y-2" data-testid="feedback-block">
      {feedback && (
        <section className="rounded-xl border border-theme-border p-3">
          <h2 className="text-sm font-bold text-theme-text">{t.feedbackHeading}</h2>
          <p className="mt-1 whitespace-pre-wrap text-sm text-theme-text-secondary">{feedback.message}</p>
          {feedback.learning.length > 0 && (
            <>
              <h3 className="mt-2 text-sm font-bold text-theme-text">{t.learningHeading}</h3>
              <ul className="list-disc pl-5 text-sm" data-testid="feedback-learning">
                {feedback.learning.map((item) => (
                  <li key={item.id}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">{item.title}</a>
                    {item.provider ? ` (${item.provider})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
      {reapply && <p className="text-sm text-theme-text-secondary" data-testid="reapply-date">{format(t.reapplyOn, { date: reapply })}</p>}
    </div>
  );
}

/** The consent text with a note when it came back in another language than the one asked for. */
function ConsentBody({ consent }: { consent: { text: string; language: string } }) {
  const { t, lang } = useLang();
  return (
    <>
      {consent.language !== lang && <p className="text-xs text-theme-muted" data-testid="consent-language-note">{t.consentLanguageNote}</p>}
      <p className="whitespace-pre-wrap text-xs text-theme-text-secondary">{consent.text}</p>
    </>
  );
}

/** A rejected candidate may ask to be kept for 12 months. The box is unticked, optional, and its own consent. */
export function TalentPoolOffer({ app, entry, onJoined }: { app: Application; entry?: TalentEntry; onJoined: () => void }) {
  const { t, lang } = useLang();
  const [text, setText] = useState<ConsentText | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (entry?.status === "active") return;
    let cancelled = false;
    getConsentText("talent_pool", lang)
      .then((data) => { if (!cancelled) setText(data); })
      .catch(() => { if (!cancelled) setError(t.consentLoadError); });
    return () => { cancelled = true; };
  }, [entry?.status, lang, t.consentLoadError]);

  if (entry?.status === "active") return <p className="mt-3 text-sm text-theme-text" data-testid="pool-joined">{t.poolJoined}</p>;

  const join = async () => {
    if (!text) return;
    setBusy(true);
    setError("");
    try {
      await joinTalentPool(app.id, text);
      onJoined();
    } catch (err) {
      setError(err instanceof HiringError && err.status === 409 && typeof err.detail === "string" ? err.detail : t.genericError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-3 space-y-2 rounded-xl border border-theme-border p-3" data-testid="pool-offer">
      <label className="flex items-start gap-2 text-sm text-theme-text">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1" />
        <span>{t.poolConsentLabel}</span>
      </label>
      {text && (
        <details>
          <summary className="cursor-pointer text-xs text-blue-400 underline">{t.poolConsentText}</summary>
          <div className="mt-1 space-y-1"><ConsentBody consent={text} /></div>
        </details>
      )}
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      <button onClick={join} disabled={!agreed || !text || busy} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-bold text-white disabled:opacity-50">
        {busy ? t.poolJoining : t.poolJoin}
      </button>
    </section>
  );
}

/** For a hire only. The server answers 409 for anyone else, and then nothing is shown. */
export function OnboardingConsentPrompt({ applicationId }: { applicationId: number }) {
  const { t, lang } = useLang();
  const [consent, setConsent] = useState<OnboardingConsent | null>(null);
  const [declined, setDeclined] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getOnboardingConsent(applicationId, lang)
      .then((data) => {
        if (cancelled) return;
        setConsent(data);
        setDeclined(localStorage.getItem(declinedKey(applicationId)) === "1");
      })
      .catch(() => { /* not a hire: no prompt */ });
    return () => { cancelled = true; };
  }, [applicationId, lang]);

  if (!consent) return null;
  if (consent.granted) return <p className="mt-3 text-sm text-theme-text" data-testid="onboarding-granted">{t.onboardingGranted}</p>;
  if (declined) return <p className="mt-3 text-sm text-theme-text-secondary" data-testid="onboarding-declined">{t.onboardingDeclined}</p>;

  const agree = async () => {
    setBusy(true);
    setError("");
    try {
      setConsent(await grantOnboardingConsent(applicationId, consent, lang));
    } catch {
      setError(t.genericError);
    } finally {
      setBusy(false);
    }
  };
  const decline = () => {
    localStorage.setItem(declinedKey(applicationId), "1");
    setDeclined(true);
  };

  return (
    <section className="mt-3 space-y-2 rounded-xl border border-theme-border p-3" data-testid="onboarding-consent">
      <h2 className="text-sm font-bold text-theme-text">{t.onboardingHeading}</h2>
      <p className="text-sm text-theme-text-secondary">{t.onboardingBody}</p>
      <ConsentBody consent={consent} />
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button onClick={agree} disabled={busy} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-bold text-white disabled:opacity-50">{t.onboardingAgree}</button>
        <button onClick={decline} disabled={busy} className="rounded-lg bg-theme-surface px-3 py-1.5 text-sm text-theme-text">{t.onboardingDecline}</button>
      </div>
    </section>
  );
}
