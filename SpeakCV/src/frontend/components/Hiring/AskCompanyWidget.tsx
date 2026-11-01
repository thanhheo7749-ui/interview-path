"use client";

import { useState } from "react";
import { askCompany, AskAnswer, HiringError } from "@/services/hiring";
import { format, useLang } from "@/lib/i18n";

/** Ask the company a question. Answers and sources come from the company's own documents. */
export default function AskCompanyWidget({ companySlug }: { companySlug: string }) {
  const { t } = useLang();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskAnswer | null>(null);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await askCompany(companySlug, question.trim()));
    } catch (err) {
      const status = err instanceof HiringError ? err.status : 0;
      setError(status === 429 ? t.askRate : status === 503 ? t.askUnavailable : t.genericError);
    } finally {
      setBusy(false);
    }
  };

  // The server already words not_found and conflict in the question's language; the local text is the fallback.
  const shown = result
    ? result.answer || (result.state === "conflict" ? t.askConflict : result.state === "not_found" ? t.askNotFound : "")
    : "";

  return (
    <section className="rounded-2xl border border-theme-border bg-theme-surface p-5 space-y-3" aria-labelledby="ask-title">
      <h2 id="ask-title" className="text-lg font-bold text-theme-text">{t.askTitle}</h2>
      <p className="text-sm text-theme-text-secondary">{t.askHint}</p>
      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          placeholder={t.askPlaceholder}
          aria-label={t.askPlaceholder}
          className="flex-1 rounded-lg bg-theme-secondary border border-theme-border px-3 py-2 text-theme-text"
        />
        <button type="submit" disabled={busy || !question.trim()} className="px-4 py-2 rounded-lg bg-blue-600 text-white font-bold disabled:opacity-50">
          {busy ? t.asking : t.ask}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      {result && (
        <div role="status" className="space-y-2">
          <p
            className={`text-sm whitespace-pre-wrap ${
              result.state === "answered" ? "text-theme-text" : "text-amber-300"
            }`}
          >
            {shown}
          </p>
          {result.state === "answered" && result.citations.length > 0 && (
            <div className="text-xs text-theme-muted">
              <p className="font-bold">{t.askSources}</p>
              <ul className="list-disc pl-5">
                {result.citations.map((c, i) => (
                  <li key={i}>
                    {c.title}
                    {c.page != null ? `, ${format(t.askPage, { n: c.page })}` : ""}
                    {c.effective_date ? `, ${c.effective_date}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
