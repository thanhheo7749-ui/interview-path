import { API_URL, authHeader } from "@/services/api";

export class HiringApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

async function fail(res: Response): Promise<never> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  const message = typeof detail === "string" ? detail : detail?.message || `HTTP ${res.status}`;
  throw new HiringApiError(res.status, message, detail);
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...authHeader(), ...(init.headers || {}) },
  });
  if (!res.ok) await fail(res);
  return res.json() as Promise<T>;
}

export interface MyApplication {
  id: number;
  alias: string;
  status: string;
  job_title: string;
  company_name: string;
}

export interface ConsentText {
  purpose: string;
  version: string;
  text: string;
}

export interface SessionState {
  session_id: number;
  status: string;
  position: number | null;
  question_text: string | null;
  question_source: string | null;
  why: string | null;
  total: number;
  time_left_seconds: number;
  is_followup: boolean;
  notice: string | null;
}

export const getApplication = (id: number) => call<MyApplication>(`/applications/${id}`);

export const getConsent = (purpose: string, language: string) =>
  call<ConsentText>(`/consents/${purpose}?language=${encodeURIComponent(language)}`);

export const declineRecording = (applicationId: number) =>
  call<MyApplication>(`/applications/${applicationId}/decline-recording`, { method: "POST" });

export const startSession = (applicationId: number, consentVersion: string, language: string) =>
  call<SessionState>(`/screening/${applicationId}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ consent_version: consentVersion, language }),
  });

export const getSessionState = (sessionId: number) => call<SessionState>(`/screening/${sessionId}/state`);

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const UPLOAD_ATTEMPTS = 3;
const BACKOFF_MS = 1000;

/**
 * Upload one answer. Network failures and 5xx are retried with backoff; this is safe because the server is
 * idempotent per position. If every attempt fails, the caller should resume from getSessionState.
 */
export async function submitAnswer(sessionId: number, position: number, blob: Blob): Promise<SessionState> {
  let last: unknown;
  for (let attempt = 0; attempt < UPLOAD_ATTEMPTS; attempt++) {
    if (attempt > 0) await sleep(BACKOFF_MS * 2 ** (attempt - 1));
    try {
      const form = new FormData();
      form.append("file", blob, "answer");
      const res = await fetch(`${API_URL}/screening/${sessionId}/turns/${position}/answer`, {
        method: "POST",
        headers: authHeader(),
        body: form,
      });
      if (res.ok) return (await res.json()) as SessionState;
      if (res.status < 500) await fail(res); // a client error will not change on retry
      last = new HiringApiError(res.status, `HTTP ${res.status}`);
    } catch (error) {
      if (error instanceof HiringApiError && error.status < 500) throw error;
      last = error;
    }
  }
  throw last instanceof Error ? last : new Error("Upload failed");
}

/** The spoken question, or null when the server has no audio (204) or fails; the text is enough. */
export async function fetchQuestionAudio(sessionId: number, position: number): Promise<Blob | null> {
  try {
    const res = await fetch(`${API_URL}/screening/${sessionId}/turns/${position}/question-audio`, { headers: authHeader() });
    if (!res.ok || res.status === 204) return null;
    const blob = await res.blob();
    return blob.size ? blob : null;
  } catch {
    return null;
  }
}
