import type { Lang } from "@/lib/i18n";

export type InterviewWindow = { start: string; end: string; timezone: string | null };
export type WindowState = "before" | "open" | "after";

/** Where `now` falls relative to the job's scheduling window. */
export function windowState(win: InterviewWindow, now: number): WindowState {
  const start = Date.parse(win.start);
  const end = Date.parse(win.end);
  if (now < start) return "before";
  if (now > end) return "after";
  return "open";
}

const LOCALE: Record<Lang, string> = { en: "en-US", vi: "vi-VN" };

/** Formats an ISO instant in the window's timezone. An invalid IANA name falls back to the local timezone. */
export function formatWindowTime(iso: string, timezone: string | null, lang: Lang): string {
  const date = new Date(iso);
  try {
    return new Intl.DateTimeFormat(LOCALE[lang], { dateStyle: "medium", timeStyle: "short", timeZone: timezone ?? undefined }).format(date);
  } catch {
    return new Intl.DateTimeFormat(LOCALE[lang], { dateStyle: "medium", timeStyle: "short" }).format(date);
  }
}
