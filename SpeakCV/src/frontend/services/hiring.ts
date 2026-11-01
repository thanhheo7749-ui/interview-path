import { API_URL, authHeader } from "@/services/api";

/** Error from a hiring route. `detail` is whatever the server sent: a string, or an object for some 409s. */
export class HiringError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
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
  | "reading_cv" | "cv_unreadable" | "invited" | "interview_in_progress" | "with_hr" | "withdrawn";

export interface Application {
  id: number;
  alias: string;
  status: ApplicationStatus;
  job_title: string;
  company_name: string;
  company_slug: string;
  is_sample: boolean;
  interview_languages: string[];
  created_at: string | null;
  withdraw_reason: string | null;
  processing_error: string | null;
}

export interface FitItem { requirement_id: number; text: string; fit: "matches" | "partly" | "not_seen" }
export interface StyleItem { type: string; title: string; body: string }
export interface Fit { requirements: FitItem[]; team_style: StyleItem[] }
export interface ConsentText { purpose: string; version: string; text: string }

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
  language: string;
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
  request<ConsentText>(`/consents/${encodeURIComponent(purpose)}?language=${language}`);

export function applyToJob(slug: string, file: File, consentVersion: string, src?: string | null) {
  const form = new FormData();
  form.append("file", file);
  form.append("consent_version", consentVersion);
  if (src) form.append("src", src);
  return request<Application>(`/public/jobs/${encodeURIComponent(slug)}/apply`, { method: "POST", body: form });
}

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
