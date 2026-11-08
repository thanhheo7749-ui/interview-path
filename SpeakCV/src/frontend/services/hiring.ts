import { API_URL, authHeader } from "@/services/api";

/** Error from a hiring route. `detail` is whatever the server sent: a string, or an object for some 409s. */
export class HiringError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : (detail as { message?: string } | null)?.message || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export const RECORDING_CONSENT_WITHDRAWN = "recording_consent_withdrawn";
export const CV_CONSENT_WITHDRAWN = "cv_consent_withdrawn";
export const OUTSIDE_INTERVIEW_WINDOW = "OUTSIDE_INTERVIEW_WINDOW";

/** The code a 409 carries when retrying can never work, because the candidate withdrew a consent. */
export function errorCode(error: unknown): string | null {
  if (!(error instanceof HiringError) || typeof error.detail !== "object" || error.detail === null) return null;
  return (error.detail as { code?: string }).code ?? null;
}

export interface PublicRequirement { text: string; must_have: boolean }
export interface PublicJob {
  slug: string;
  title: string;
  description: string;
  company_name: string;
  company_slug: string;
  is_sample: boolean;
  interview_languages: string[];
  status: string;
  can_apply: boolean;
  requirements: PublicRequirement[];
}

export type ApplicationStatus =
  | "reading_cv" | "cv_unreadable" | "invited" | "interview_in_progress" | "with_hr" | "decided" | "withdrawn";

export interface Application {
  id: number;
  alias: string;
  status: ApplicationStatus;
  job_title: string;
  job_slug: string | null;
  company_name: string;
  company_slug: string;
  is_sample: boolean;
  interview_languages: string[];
  created_at: string | null;
  withdraw_reason: string | null;
  processing_error: string | null;
  decision: "approved" | "rejected" | null;
  /** A fixed code for why the CV failed, never the text of the failure. */
  failure_reason: string | null;
  /** Whether this deployment can send email at all. */
  email_enabled: boolean;
  /** The candidate's own account email, only once approved. */
  contact_email: string | null;
  /** Only what HR approved and sent. */
  feedback?: Feedback | null;
  /** Once rejected: the first day this job takes a new application. */
  reapply_after?: string | null;
  /** The job's interview scheduling window, or null when the job does not schedule interviews. */
  interview_window?: { start: string; end: string; timezone: string | null } | null;
  final_outcome?: "hired" | "not_hired" | null;
  access_token?: string | null;
}

export interface LearningItem { id: number; title: string; url: string; provider: string; language: string }
export interface Feedback {
  application_id: number;
  language: string;
  message: string;
  learning: LearningItem[];
  sent_at: string | null;
}

export type TalentStatus = "active" | "expired" | "left";
export interface TalentEntry {
  id: number;
  application_id: number;
  consent_id: number;
  status: TalentStatus;
  expires_at: string;
  job_title: string;
  company_name: string;
}

/** `language` is the language of `text`, which may not be the one asked for. */
export interface OnboardingConsent {
  purpose: string;
  version: string;
  language: string;
  text: string;
  granted: boolean;
  consent_id: number | null;
}

export interface FitItem { requirement_id: number; text: string; fit: "matches" | "partly" | "not_seen" | "not_assessed" }
export interface StyleItem { type: string; title: string; body: string }
export interface Fit { requirements: FitItem[]; team_style: StyleItem[] }
/** `language` is the language of `text`, which may not be the one asked for. It is what the consent ledger records. */
export interface ConsentText { purpose: string; version: string; language: string; text: string }

export interface AskCitation { title: string; page: number | null; effective_date: string | null; shared: boolean }
export interface AskAnswer {
  state: string; // "answered", "not_found" or "conflict"
  answer: string;
  citations: AskCitation[];
  question_id: number;
}

export interface MyConsent {
  id: number;
  purpose: string;
  version: string;
  language: string | null;
  granted_at: string | null;
  withdrawn_at: string | null;
  job_title: string | null;
}

async function request<T>(path: string, options: RequestInit = {}, auth = true): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (auth) Object.assign(headers, authHeader());
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new HiringError(res.status, body?.detail ?? null);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getPublicJob = (slug: string, src?: string | null) =>
  request<PublicJob>(`/public/jobs/${encodeURIComponent(slug)}${src ? `?src=${encodeURIComponent(src)}` : ""}`, {}, false);

export const getConsentText = (purpose: string, language = "en") =>
  request<ConsentText>(`/public/consents/${encodeURIComponent(purpose)}?language=${language}`, {}, false);

export function applyToJob(
  slug: string,
  file: File,
  consentVersion: string,
  consentLanguage: string,
  src?: string | null,
  candidateEmail?: string,
  candidateName?: string,
) {
  const form = new FormData();
  form.append("file", file);
  form.append("consent_version", consentVersion);
  form.append("consent_language", consentLanguage);
  if (src) form.append("src", src);
  if (candidateEmail?.trim()) form.append("candidate_email", candidateEmail.trim());
  if (candidateName?.trim()) form.append("candidate_name", candidateName.trim());
  return request<Application>(`/public/jobs/${encodeURIComponent(slug)}/apply`, { method: "POST", body: form });
}

export interface ClaimInfo {
  application_id: number;
  candidate_name: string | null;
  candidate_email: string | null;
  job_title: string;
  company_name: string;
  company_id: number;
  stage: string;
  consent_version: string;
}

export const getClaimInfo = (token: string) =>
  request<ClaimInfo>(`/public/applications/claim/${encodeURIComponent(token)}`, {}, false);

export const claimApplication = (token: string, consentVersion: string, consentLanguage = "en") =>
  request<{ application_id: number; access_token: string; email: string }>(
    "/public/applications/claim",
    json({ token, consent_version: consentVersion, consent_language: consentLanguage }),
    false,
  );

export const listMyApplications = () => request<Application[]>("/me/applications");
export const getApplication = (id: number) => request<Application>(`/applications/${id}`);
export const getFit = (id: number) => request<Fit>(`/applications/${id}/fit`);
export const withdrawApplication = (id: number, reason?: string) =>
  request<Application>(`/applications/${id}/withdraw`, json({ reason: reason?.trim() || null }));

export function reuploadCv(id: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<Application>(`/applications/${id}/reupload`, { method: "POST", body: form });
}

export const declineRecording = (id: number) =>
  request<Application>(`/applications/${id}/decline-recording`, { method: "POST" });

export const askCompany = (companySlug: string, question: string) =>
  request<AskAnswer>(`/public/companies/${encodeURIComponent(companySlug)}/ask`, json({ question }));

export const listMyConsents = () => request<MyConsent[]>("/me/consents");
export const withdrawConsent = (id: number) => request<unknown>(`/me/consents/${id}/withdraw`, { method: "POST" });
export const deleteMyApplication = (id: number) => request<void>(`/me/applications/${id}`, { method: "DELETE" });

// ---------- recorded interview ----------

async function fail(res: Response): Promise<never> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  throw new HiringError(res.status, detail);
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...authHeader(), ...(init.headers || {}) },
  });
  if (!res.ok) await fail(res);
  return res.json() as Promise<T>;
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

/** The text for this application: it states the retention period of the company that receives the recording. */
export const getApplicationConsent = (applicationId: number, purpose: string, language: string) =>
  call<ConsentText>(`/applications/${applicationId}/consents/${purpose}?language=${encodeURIComponent(language)}`);

export const startSession = (applicationId: number, consent: ConsentText, language: string) =>
  call<SessionState>(`/screening/${applicationId}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ consent_version: consent.version, language, consent_language: consent.language }),
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
      last = new HiringError(res.status, `HTTP ${res.status}`);
    } catch (error) {
      if (error instanceof HiringError && error.status < 500) throw error;
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

// ---------- after the decision: talent pool and onboarding consent ----------

export const listMyTalentEntries = () => request<TalentEntry[]>("/me/talent-pool");
export const joinTalentPool = (applicationId: number, consent: ConsentText) =>
  request<TalentEntry>(`/applications/${applicationId}/talent-pool`, json({ consent_version: consent.version, consent_language: consent.language }));
/** A second call after the entry was anonymized returns 404: the caller treats that as done. */
export const leaveTalentPool = (entryId: number) => request<{ id: number; status: string }>(`/talent-pool/${entryId}/leave`, { method: "POST" });

/** 409 means this application is not a hire, so there is nothing to ask. */
export const getOnboardingConsent = (applicationId: number, language: string) =>
  request<OnboardingConsent>(`/applications/${applicationId}/onboarding-consent?language=${encodeURIComponent(language)}`);
export const grantOnboardingConsent = (applicationId: number, consent: OnboardingConsent, language: string) =>
  request<OnboardingConsent>(`/applications/${applicationId}/onboarding-consent`, json({ version: consent.version, language }));
