"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { MicCheck } from "@/components/Hiring/MicCheck";
import { MAX_ANSWER_SECONDS, supportsRecording, useAnswerRecorder } from "@/hooks/useAnswerRecorder";
import { detectLocale, screeningText, type Locale } from "@/lib/i18n";
import {
  CV_CONSENT_WITHDRAWN,
  HiringError,
  OUTSIDE_INTERVIEW_WINDOW,
  RECORDING_CONSENT_WITHDRAWN,
  declineRecording,
  errorCode,
  fetchQuestionAudio,
  getApplication,
  getApplicationConsent,
  getSessionState,
  startSession,
  submitAnswer,
  type ConsentText,
  type SessionState,
} from "@/services/hiring";

const CONSENT_PURPOSE = "recording_screening";
const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "vi", label: "Tiếng Việt" },
  { code: "ko", label: "한국어" },
];
const ACTIVE = ["in_progress", "closing", "paused"];

type Phase = "loading" | "message" | "preflight" | "session" | "declined";

function formatClock(seconds: number): string {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function ScreeningRoom({ applicationId }: { applicationId: number }) {
  const [locale] = useState<Locale>(() => detectLocale());
  const text = screeningText[locale];
  const [phase, setPhase] = useState<Phase>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [language, setLanguage] = useState<string>(locale);
  const [languages, setLanguages] = useState(LANGUAGES);
  const [consent, setConsent] = useState<ConsentText | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [starting, setStarting] = useState(false);
  const [confirmingDecline, setConfirmingDecline] = useState(false);

  const [session, setSession] = useState<SessionState | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const pendingRef = useRef<{ position: number; blob: Blob } | null>(null);
  const sessionRef = useRef<SessionState | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const adoptStream = useCallback((next: MediaStream) => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = next;
    setStream(next);
  }, []);

  // Release the microphone, question audio and anything playing when the page goes away.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, []);

  // A message with no retry, and the microphone let go.
  const endWith = useCallback((final: string) => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStream(null);
    pendingRef.current = null;
    setMessage(final);
    setPhase("message");
  }, []);

  const applyState = useCallback((next: SessionState) => {
    sessionRef.current = next;
    setSession(next);
    setRemaining(next.time_left_seconds);
    setUploadFailed(false);
    pendingRef.current = null;
    setPhase("session");
  }, []);

  // Load the application and decide where the candidate is. A returning candidate resumes at the current question.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!supportsRecording()) {
        setMessage(text.unsupported);
        setPhase("message");
        return;
      }
      try {
        const application = await getApplication(applicationId);
        if (cancelled) return;
        const offered = LANGUAGES.filter((l) => application.interview_languages?.includes(l.code));
        // The consent text follows the interview language shown, so the two never differ.
        const initial = offered.length > 0 && !offered.some((l) => l.code === locale) ? offered[0].code : locale;
        if (offered.length > 0) {
          setLanguages(offered);
          setLanguage(initial);
        }
        if (application.status === "invited" || application.status === "interview_in_progress") {
          const current = await getApplicationConsent(applicationId, CONSENT_PURPOSE, initial);
          if (cancelled) return;
          setConsent(current);
          if (application.status === "interview_in_progress") {
            // Starting again returns the running session; the consent and language sent are not used then.
            const resumed = await startSession(applicationId, current, initial);
            if (!cancelled) applyState(resumed);
            return;
          }
          setPhase("preflight");
        } else {
          setMessage(application.status === "with_hr" ? text.withHr : text.notInvited);
          setPhase("message");
        }
      } catch (e) {
        if (cancelled) return;
        setMessage(e instanceof HiringError && e.status === 404 ? text.notFound : e instanceof Error ? e.message : text.genericError);
        setPhase("message");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applicationId, applyState, locale, text]);

  // Time left counts down locally between states; every state from the server resets it.
  useEffect(() => {
    if (phase !== "session") return;
    const timer = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const changeLanguage = async (code: string) => {
    setLanguage(code);
    try {
      setConsent(await getApplicationConsent(applicationId, CONSENT_PURPOSE, code));
    } catch {
      /* keep the text already shown */
    }
  };

  const handleStart = async () => {
    if (!consent || !agreed || !stream) return;
    setStarting(true);
    setError(null);
    try {
      applyState(await startSession(applicationId, consent, language));
    } catch (e) {
      if (errorCode(e) === CV_CONSENT_WITHDRAWN) {
        endWith(text.cvConsentWithdrawn);
        return;
      }
      if (errorCode(e) === OUTSIDE_INTERVIEW_WINDOW) {
        endWith(text.outsideWindow);
        return;
      }
      if (e instanceof HiringError && e.status === 409 && typeof e.detail === "object") {
        setAgreed(false);
        setConsent(await getApplicationConsent(applicationId, CONSENT_PURPOSE, language).catch(() => consent));
      }
      setError(e instanceof Error ? e.message : text.genericError);
    } finally {
      setStarting(false);
    }
  };

  const handleDecline = async () => {
    setError(null);
    try {
      await declineRecording(applicationId);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setStream(null);
      setPhase("declined");
    } catch (e) {
      setConfirmingDecline(false);
      setError(e instanceof Error ? e.message : text.genericError);
    }
  };

  // Send one answer. If the connection drops for good, ask the server where we are before offering a resend:
  // the answer may have been stored even though the reply was lost.
  const send = useCallback(
    async (position: number, blob: Blob) => {
      const current = sessionRef.current;
      if (!current) return;
      pendingRef.current = { position, blob };
      setUploading(true);
      setUploadFailed(false);
      try {
        applyState(await submitAnswer(current.session_id, position, blob));
      } catch (e) {
        if (errorCode(e) === RECORDING_CONSENT_WITHDRAWN) {
          endWith(text.recordingConsentWithdrawn);
          return;
        }
        try {
          const latest = await getSessionState(current.session_id);
          if (latest.position !== position || !ACTIVE.includes(latest.status)) {
            applyState(latest);
          } else {
            setUploadFailed(true);
          }
        } catch {
          setUploadFailed(true);
        }
      } finally {
        setUploading(false);
      }
    },
    [applyState, endWith, text.recordingConsentWithdrawn],
  );

  const position = session?.position ?? null;
  const recorder = useAnswerRecorder(stream, (blob) => {
    if (position !== null) void send(position, blob);
  });

  // Speak the question when audio is available; the text is always shown, so a failure costs nothing.
  const sessionId = session?.session_id;
  useEffect(() => {
    if (sessionId === undefined || position === null) return;
    let cancelled = false;
    let url: string | null = null;
    (async () => {
      const blob = await fetchQuestionAudio(sessionId, position);
      if (cancelled || !blob) return;
      url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch(() => undefined);
    })();
    return () => {
      cancelled = true;
      audioRef.current?.pause();
      audioRef.current = null;
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId, position]);

  // The recorder stops and sends itself at 3 minutes, or when the time left reaches 0, whichever is first.
  const startRecording = () => {
    audioRef.current?.pause();
    recorder.start(Math.min(MAX_ANSWER_SECONDS, remaining));
  };

  // Time ran out while nothing was recording or being sent: ask the server, which finishes the interview.
  const { isRecording } = recorder;
  useEffect(() => {
    if (phase !== "session" || remaining > 0 || uploading || isRecording) return;
    const current = sessionRef.current;
    if (!current || !ACTIVE.includes(current.status)) return;
    getSessionState(current.session_id).then(applyState, () => undefined);
  }, [phase, remaining, uploading, isRecording, applyState]);

  const back = (
    <Link href="/applications" className="mt-6 inline-block rounded-xl bg-blue-600 px-4 py-2 font-bold text-white hover:bg-blue-700">
      {text.back}
    </Link>
  );

  const shell = (children: React.ReactNode) => (
    <main className="min-h-screen bg-theme-secondary p-4 text-theme-text">
      <div className="mx-auto max-w-2xl space-y-4 pt-8">
        <h1 className="text-2xl font-bold">{text.title}</h1>
        {children}
      </div>
    </main>
  );

  if (phase === "loading") return shell(<p>{text.loading}</p>);

  if (phase === "message" || phase === "declined") {
    return shell(
      <div>
        <p role="status">{phase === "declined" ? text.declined : message}</p>
        {back}
      </div>,
    );
  }

  if (phase === "preflight") {
    return shell(
      <>
        <MicCheck text={text} onStream={adoptStream} />
        <section className="rounded-2xl border border-theme-border bg-theme-primary p-5">
          <label className="block text-sm font-bold" htmlFor="interview-language">
            {text.languageLabel}
          </label>
          <select
            id="interview-language"
            value={language}
            onChange={(e) => void changeLanguage(e.target.value)}
            className="mt-2 w-full rounded-xl border border-theme-border bg-theme-secondary p-3"
          >
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-theme-text-secondary">{text.languageHint}</p>
        </section>
        <section className="rounded-2xl border border-theme-border bg-theme-primary p-5">
          <h2 className="font-bold">{text.consentTitle}</h2>
          <p className="mt-2 whitespace-pre-line text-sm">{consent?.text}</p>
          <p className="mt-2 text-sm font-semibold">{text.consentOnly}</p>
          <label className="mt-3 flex items-start gap-2 text-sm">
            <input
              data-testid="consent-recording"
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-1"
            />
            <span>{text.consentCheckbox}</span>
          </label>
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {error}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              data-testid="start-session"
              onClick={handleStart}
              disabled={!agreed || !stream || !consent || starting}
              className="rounded-xl bg-blue-600 px-5 py-3 font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {starting ? text.starting : text.start}
            </button>
            {!confirmingDecline && (
              <button
                type="button"
                data-testid="decline-recording"
                onClick={() => setConfirmingDecline(true)}
                className="rounded-xl border border-theme-border px-5 py-3 font-bold hover:bg-theme-secondary"
              >
                {text.decline}
              </button>
            )}
          </div>
          {confirmingDecline && (
            <div role="alertdialog" className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
              <p>{text.declineWarn}</p>
              <div className="mt-3 flex gap-3">
                <button
                  type="button"
                  data-testid="confirm-decline"
                  onClick={handleDecline}
                  className="rounded-lg bg-amber-600 px-4 py-2 font-bold text-white"
                >
                  {text.declineConfirm}
                </button>
                <button type="button" onClick={() => setConfirmingDecline(false)} className="rounded-lg border border-amber-400 px-4 py-2 font-bold">
                  {text.declineCancel}
                </button>
              </div>
            </div>
          )}
        </section>
      </>,
    );
  }

  // phase === "session"
  const state = session!;
  if (state.status === "completed") {
    return shell(
      <div data-testid="session-complete">
        {state.notice === "time_up" && (
          <p role="status" data-testid="time-up-notice" className="mb-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            {text.timeUp}
          </p>
        )}
        <p role="status">{text.completed}</p>
        {back}
      </div>,
    );
  }
  if (!ACTIVE.includes(state.status) || state.position === null) {
    return shell(
      <div>
        <p role="status">{state.status === "abandoned" ? text.abandoned : text.withHr}</p>
        {back}
      </div>,
    );
  }

  // The state of the interview and what happened to the answer just sent can both apply, so both are shown: a failed
  // recording while the interview is wrapping up must not look like nothing happened.
  const notices = [
    state.status === "paused" ? text.paused : state.status === "closing" ? text.closing : null,
    state.notice === "repeat" ? text.repeat : state.notice === "retry" ? text.retry : null,
  ].filter((item): item is string => item !== null);
  const busy = uploading || recorder.isRecording;
  const answeredIndex = state.position;

  return shell(
    <>
      <div
        data-testid="recording-indicator"
        data-recording={recorder.isRecording ? "true" : "false"}
        role="status"
        className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 px-4 py-2 text-sm font-bold text-red-700"
      >
        <span className={`h-3 w-3 rounded-full bg-red-600 ${recorder.isRecording ? "animate-pulse" : ""}`} />
        {recorder.isRecording ? text.recordingOn : text.recordingSession}
      </div>

      <div className="flex items-center justify-between text-sm text-theme-text-secondary">
        <span data-testid="question-progress">{text.questionOf(answeredIndex, state.total)}</span>
        <span>
          {text.timeLeft}: <span data-testid="time-left">{formatClock(remaining)}</span>
        </span>
      </div>

      <section className="rounded-2xl border border-theme-border bg-theme-primary p-5">
        {state.is_followup && <p className="mb-1 text-xs font-bold uppercase text-blue-600">{text.followup}</p>}
        <p data-testid="question-text" className="text-lg font-semibold">
          {state.question_text}
        </p>
        {state.why && (
          <p className="mt-3 text-sm text-theme-text-secondary">
            <span className="font-bold">{text.why}:</span> {state.why}
          </p>
        )}
      </section>

      {notices.map((notice) => (
        <p key={notice} role="status" data-testid="session-notice" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {notice}
        </p>
      ))}

      {!stream && <MicCheck text={text} onStream={adoptStream} />}

      <div className="flex flex-wrap items-center gap-3">
        {!recorder.isRecording ? (
          <button
            type="button"
            data-testid="record-answer"
            onClick={startRecording}
            disabled={!stream || uploading || uploadFailed}
            className="rounded-xl bg-blue-600 px-5 py-3 font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {text.record}
          </button>
        ) : (
          <button
            type="button"
            data-testid="stop-answer"
            onClick={recorder.stop}
            className="rounded-xl bg-red-600 px-5 py-3 font-bold text-white hover:bg-red-700"
          >
            {text.stop} ({formatClock(recorder.elapsed)} / {formatClock(recorder.limitSeconds)})
          </button>
        )}
        {uploadFailed && pendingRef.current && (
          <button
            type="button"
            onClick={() => pendingRef.current && void send(pendingRef.current.position, pendingRef.current.blob)}
            className="rounded-xl border border-theme-border px-5 py-3 font-bold hover:bg-theme-primary"
          >
            {text.retrySend}
          </button>
        )}
      </div>
      {!busy && <p className="text-xs text-theme-text-secondary">{text.recordingAuto}</p>}
      {uploading && <p role="status">{text.uploading}</p>}
      {uploadFailed && (
        <p role="alert" className="text-sm text-red-600">
          {text.uploadFailed}
        </p>
      )}
      {recorder.error && (
        <p role="alert" className="text-sm text-red-600">
          {text.recordError}
        </p>
      )}
    </>,
  );
}
