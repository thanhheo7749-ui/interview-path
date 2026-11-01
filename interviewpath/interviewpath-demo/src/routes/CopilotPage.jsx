import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import DemoAiNotice from '../components/DemoAiNotice.jsx';
import { askCopilot } from '../lib/kb.js';

const MAX_QUESTION = 1000;
const STATE_STYLES = {
  answered: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  conflict: 'border-amber-200 bg-amber-50 text-amber-800',
  not_found: 'border-slate-200 bg-slate-100 text-slate-700',
};

function errorKey(error) {
  if (error?.status === 503) return 'copilot.errors.unavailable';
  if (error?.status === 502) return 'copilot.errors.provider';
  return 'copilot.errors.generic';
}

function Citation({ citation }) {
  const { t, i18n } = useTranslation();
  const details = [];
  if (citation.shared) {
    if (citation.page != null) details.push(t('copilot.page', { page: citation.page }));
    if (citation.effective_date) {
      details.push(t('copilot.effective', { date: new Date(`${citation.effective_date}T00:00:00`).toLocaleDateString(i18n.language) }));
    }
  }
  return (
    <li data-testid="copilot-citation" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
      <span className="font-bold text-slate-950">{citation.shared ? citation.title : t('copilot.notShared')}</span>
      {details.length > 0 && <span className="ml-2 text-xs font-semibold text-slate-500">{details.join(' · ')}</span>}
    </li>
  );
}

function Exchange({ item }) {
  const { t } = useTranslation();
  const { question, status, response, error } = item;
  return (
    <li className="space-y-3" data-testid="copilot-exchange">
      <div className="ml-auto max-w-[85%] rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-card">
        <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">{t('copilot.you')}</p>
        <p className="whitespace-pre-wrap break-words">{question}</p>
      </div>

      {status === 'pending' && (
        <p role="status" className="text-sm font-semibold text-slate-500">
          {t('copilot.asking')}
        </p>
      )}

      {status === 'error' && (
        <p role="alert" className="max-w-[85%] rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-800">
          {t(errorKey(error))}
        </p>
      )}

      {status === 'done' && (
        <div
          data-testid="copilot-answer"
          data-state={response.state}
          className="max-w-[85%] space-y-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-card"
        >
          <span className={`inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.1em] ${STATE_STYLES[response.state] ?? STATE_STYLES.not_found}`}>
            {t(`copilot.states.${response.state}`, { defaultValue: response.state })}
          </span>
          {response.state === 'conflict' && (
            <p role="note" className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800">
              {t('copilot.conflictNotice')}
            </p>
          )}
          {response.state === 'not_found' && (
            <p role="note" className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
              {t('copilot.notFoundNotice')}
            </p>
          )}
          <p className="whitespace-pre-wrap break-words text-sm text-slate-900">{response.answer}</p>
          {response.citations.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-bold uppercase tracking-[0.12em] text-slate-400">{t('copilot.sources')}</p>
              <ul className="space-y-1">
                {response.citations.map((citation, index) => (
                  <Citation key={`${citation.title}-${citation.page}-${index}`} citation={citation} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function CopilotPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [history, setHistory] = useState({ companyId: null, items: [] });
  const [text, setText] = useState('');
  const nextId = useRef(0);
  const items = history.companyId === companyId ? history.items : [];

  const patch = (id, change) =>
    setHistory((h) => (h.companyId === companyId ? { ...h, items: h.items.map((i) => (i.id === id ? { ...i, ...change } : i)) } : h));

  const submit = (event) => {
    event.preventDefault();
    const question = text.trim();
    if (!question || companyId == null) return;
    const id = (nextId.current += 1);
    setText('');
    setHistory((h) => ({ companyId, items: [...(h.companyId === companyId ? h.items : []), { id, question, status: 'pending' }] }));
    askCopilot(companyId, question)
      .then((response) => patch(id, { status: 'done', response }))
      .catch((error) => patch(id, { status: 'error', error }));
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{t('copilot.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('copilot.subtitle')}</p>
      </div>
      <DemoAiNotice />

      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-card">
        {items.length === 0 ? (
          <p className="text-sm font-semibold text-slate-500">{t('copilot.empty')}</p>
        ) : (
          <ol className="space-y-5" aria-live="polite">
            {items.map((item) => (
              <Exchange key={item.id} item={item} />
            ))}
          </ol>
        )}
      </section>

      <form onSubmit={submit} className="space-y-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <label htmlFor="copilot-question" className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">
          {t('copilot.inputLabel')}
        </label>
        <textarea
          id="copilot-question"
          value={text}
          maxLength={MAX_QUESTION}
          rows={3}
          placeholder={t('copilot.placeholder')}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-950"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400">{t('copilot.counter', { count: text.length, max: MAX_QUESTION })}</span>
          <button
            type="submit"
            disabled={!text.trim() || companyId == null}
            className="rounded-xl bg-slate-950 px-5 py-2.5 text-sm font-bold text-white shadow-card transition hover:bg-slate-800 disabled:opacity-50"
          >
            {t('copilot.send')}
          </button>
        </div>
      </form>
    </div>
  );
}

export default CopilotPage;
