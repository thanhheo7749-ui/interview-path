import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { approveFeedback, draftFeedback, getFeedback, reasonList, saveFeedback } from '../../lib/posthire.js';
import { ErrorAlert, inputClass, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// The message a rejected candidate may receive. Nothing is sent until HR approves it here or in the bulk list.
function FeedbackEditor({ companyId, appId, onChanged }) {
  const { t } = useTranslation();
  const [row, setRow] = useState(null);
  const [missing, setMissing] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reasons, setReasons] = useState([]);
  const [confirmRedraft, setConfirmRedraft] = useState(false);
  const changed = useRef(onChanged);
  useEffect(() => { changed.current = onChanged; });

  const show = useCallback((data) => {
    setRow(data);
    setMissing(false);
    setText(data.draft);
  }, []);

  // The draft is written in the background right after the rejection, so look again a few times before offering to write it.
  useEffect(() => {
    let cancelled = false;
    let timer;
    const load = (attempt) => getFeedback(companyId, appId)
      .then((data) => {
        if (cancelled) return;
        show(data);
        if (attempt > 0) changed.current?.(); // the board's count of drafts was read before this one existed
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status !== 404) setError(err.message);
        else if (attempt < 4) timer = setTimeout(() => load(attempt + 1), 1500);
        else setMissing(true);
      });
    load(0);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [companyId, appId, show]);

  const run = async (action) => {
    setBusy(true);
    setError('');
    setReasons([]);
    setConfirmRedraft(false);
    try {
      show(await action());
      await onChanged?.();
    } catch (err) {
      setError(err.message);
      setReasons(reasonList(err.data?.problems));
      // The text changed since it was read: show the current one, so the next approval is of what HR sees.
      if (err.status === 409) getFeedback(companyId, appId).then(show, () => {});
    } finally {
      setBusy(false);
    }
  };
  const approve = () => run(async () => {
    await approveFeedback(companyId, [{ application_id: appId, version: row.version }]);
    return getFeedback(companyId, appId);
  });

  const sent = row?.status === 'sent';
  const dirty = row != null && text !== row.draft;

  return (
    <section aria-labelledby="feedback-title" data-testid="feedback-editor" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <h3 id="feedback-title" className="text-sm font-extrabold text-slate-950">{t('posthire.feedback.title')}</h3>
      <p className="text-xs text-slate-600">{t('posthire.feedback.intro')}</p>
      <ErrorAlert message={error} />
      {reasons.length > 0 && (
        <ul data-testid="feedback-refusal" className="list-disc pl-5 text-xs font-semibold text-red-800">
          {reasons.map(({ code, detail }) => (
            <li key={`${code}${detail}`}>{t(`posthire.problems.${code}`, { defaultValue: code })}{detail && `: ${detail}`}</li>
          ))}
        </ul>
      )}
      {!row && !missing && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {missing && (
        <>
          <p className="text-sm text-slate-700">{t('posthire.feedback.none')}</p>
          <button type="button" disabled={busy} onClick={() => run(() => draftFeedback(companyId, appId))} className={primaryButton}>
            {busy ? t('posthire.feedback.drafting') : t('posthire.feedback.write')}
          </button>
        </>
      )}
      {row && (
        <>
          <p data-testid="feedback-status" className="text-xs font-bold text-slate-600">
            {t(`posthire.feedback.status.${row.status}`)}
          </p>
          {row.source && (
            <p data-testid={row.source === 'ai' ? 'feedback-ai-marker' : 'feedback-source'} className={row.source === 'ai' ? 'inline-block rounded-full bg-violet-50 px-2.5 py-1 text-xs font-bold text-violet-800' : 'text-xs text-slate-500'}>
              {t(`posthire.feedback.source.${row.source}`, { defaultValue: row.source })}
            </p>
          )}
          <textarea
            aria-label={t('posthire.feedback.message')}
            value={text}
            readOnly={sent}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className={`${inputClass} w-full`}
          />
          {!sent && row.problems.length > 0 && (
            <ul data-testid="feedback-problems" className="list-disc pl-5 text-xs font-semibold text-amber-800">
              {reasonList(row.problems).map(({ code, detail }) => (
                <li key={`${code}${detail}`}>{t(`posthire.problems.${code}`, { defaultValue: code })}{detail && `: ${detail}`}</li>
              ))}
            </ul>
          )}
          <div data-testid="feedback-learning">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">{t('posthire.feedback.learning')}</h4>
            {row.learning.length === 0 ? (
              <p className="text-xs text-slate-500">{t('posthire.feedback.noLearning')}</p>
            ) : (
              <ul className="mt-1 list-disc pl-5 text-sm">
                {row.learning.map((item) => (
                  <li key={item.id}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-blue-700 underline">{item.title}</a>
                    {item.provider && <span className="text-slate-500"> · {item.provider}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {!sent && (
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" disabled={busy || !dirty} onClick={() => run(() => saveFeedback(companyId, appId, text))} className={secondaryButton}>
                {t('posthire.feedback.save')}
              </button>
              <button type="button" disabled={busy || dirty} onClick={approve} className={primaryButton}>
                {t('posthire.feedback.approve')}
              </button>
              <button type="button" disabled={busy} onClick={() => setConfirmRedraft(true)} className={secondaryButton}>
                {t('posthire.feedback.redraft')}
              </button>
              {confirmRedraft && (
                <div role="alertdialog" aria-label={t('posthire.feedback.redraft')} className="basis-full space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-sm font-semibold text-amber-900">{t('posthire.feedback.redraftConfirm')}</p>
                  <div className="flex gap-2">
                    <button type="button" disabled={busy} onClick={() => run(() => draftFeedback(companyId, appId))} className={primaryButton}>{t('posthire.feedback.redraftYes')}</button>
                    <button type="button" onClick={() => setConfirmRedraft(false)} className={secondaryButton}>{t('common.cancel')}</button>
                  </div>
                </div>
              )}
              {dirty && <span className="text-xs text-slate-500">{t('posthire.feedback.saveFirst')}</span>}
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default FeedbackEditor;
