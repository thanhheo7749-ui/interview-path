import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { formatRecordingTime, generateBrief, getBrief, saveBrief, sendBrief } from '../../lib/bridges.js';
import { ConfirmBar, ErrorAlert, inputClass, primaryButton, secondaryButton } from '../KbFeedback.jsx';
import { PlayFromMoment } from './TranscriptPanel.jsx';

// The original quote stays in the language it was said or written in, whatever language the brief is in.
function QuoteLine({ point, listen }) {
  const { t } = useTranslation();
  const hasTime = point.turn_position != null && point.recording_seconds != null;
  return (
    <div className="mt-2 space-y-1">
      {point.original_quote ? (
        <blockquote data-testid="original-quote" translate="no" className="border-l-2 border-slate-300 pl-2 text-xs text-slate-700">
          {point.original_quote}
        </blockquote>
      ) : (
        <p className="text-xs italic text-slate-500">{t('bridges.brief.noQuote')}</p>
      )}
      {point.original_quote && point.quote_source && (
        <p className="text-[11px] font-semibold text-slate-500">{t(`bridges.brief.source.${point.quote_source}`, { defaultValue: point.quote_source })}</p>
      )}
      {hasTime && (
        <p data-testid="recording-time" className="text-[11px] font-semibold text-slate-500">
          {t('bridges.brief.recordingTime', { time: formatRecordingTime(point.recording_seconds), position: point.turn_position })}
        </p>
      )}
      {hasTime && listen?.(point)}
    </div>
  );
}

function Point({ point, textKey, onChange, readOnly, listen }) {
  const { t } = useTranslation();
  return (
    <li data-testid="brief-point" className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs font-bold text-slate-500">{point.label}</p>
      {readOnly ? (
        <p className="mt-1 text-sm font-semibold text-slate-900">{point[textKey]}</p>
      ) : (
        <textarea
          aria-label={t('bridges.brief.wording', { label: point.label })}
          value={point[textKey]}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          maxLength={2000}
          className={`${inputClass} mt-1 w-full`}
        />
      )}
      <QuoteLine point={point} listen={listen} />
    </li>
  );
}

function Section({ id, title, items, textKey, onItem, readOnly, listen }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby={`brief-${id}`} data-testid={`brief-${id}`}>
      <h4 id={`brief-${id}`} className="text-sm font-extrabold text-slate-950">{title}</h4>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-slate-500">{t('bridges.brief.sectionEmpty')}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.map((point, index) => (
            <Point key={`${point.evidence_id}-${index}`} point={point} textKey={textKey} readOnly={readOnly} listen={listen} onChange={(value) => onItem(index, value)} />
          ))}
        </ul>
      )}
    </section>
  );
}

// `content` is the brief as the server sent it. HR edits wording only: quotes and times are shown, never edited.
// `onChange` receives the whole changed content; without it the brief is read-only (the manager's view).
// `audioPositions` and `appId` let HR play the answer a quote came from; the manager has no recording route.
function BriefEditor({ content, onChange, companyId, appId, audioPositions }) {
  const { t } = useTranslation();
  const readOnly = !onChange;
  const edit = (section, key) => (index, value) =>
    onChange({ ...content, [section]: content[section].map((p, i) => (i === index ? { ...p, [key]: value } : p)) });

  // Playing starts the whole answer from its beginning, so the button says that instead of promising the quote's second.
  const listen = !readOnly && audioPositions
    ? (point) => audioPositions.has(point.turn_position) && (
      <PlayFromMoment companyId={companyId} appId={appId} position={point.turn_position}
        label={t('bridges.brief.playAnswer', { position: point.turn_position })} />
    )
    : null;

  return (
    <div className="space-y-4">
      {content.no_evidence && <p className="rounded-xl bg-amber-50 p-3 text-sm font-semibold text-amber-900">{content.note || t('bridges.brief.noEvidence')}</p>}
      <Section id="strengths" title={t('bridges.brief.strengths')} items={content.strengths ?? []} textKey="summary" readOnly={readOnly} listen={listen} onItem={edit('strengths', 'summary')} />
      <Section id="to-clarify" title={t('bridges.brief.toClarify')} items={content.to_clarify ?? []} textKey="summary" readOnly={readOnly} listen={listen} onItem={edit('to_clarify', 'summary')} />
      <Section id="questions" title={t('bridges.brief.questions')} items={content.questions ?? []} textKey="question" readOnly={readOnly} listen={listen} onItem={edit('questions', 'question')} />
    </div>
  );
}

const LANGUAGES = ['ko', 'vi', 'en'];

// HR's side: draft a brief from the evidence, edit the wording, mark it reviewed, and only then send it.
// The server refuses to send an unreviewed brief; the button stays off until HR has saved the wording.
export function BriefWorkflow({ companyId, appId, audioPositions }) {
  const { t } = useTranslation();
  const [language, setLanguage] = useState('ko');
  const [brief, setBrief] = useState(null); // the server's row
  const [content, setContent] = useState(null); // the wording on screen
  const [dirty, setDirty] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // A reload must show the brief the server kept: its draft, review and sent state.
  useEffect(() => {
    let cancelled = false;
    getBrief(companyId, appId)
      .then((row) => {
        if (cancelled) return;
        if (row) {
          setBrief(row);
          setContent(row.content);
          if (row.language) setLanguage(row.language);
        }
        setLoaded(true);
      })
      .catch((err) => { if (!cancelled) { setError(err.message); setLoaded(true); } });
    return () => { cancelled = true; };
  }, [companyId, appId]);

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const take = (row) => {
    setBrief(row);
    setContent(row.content);
    setDirty(false);
  };
  const generate = () => run(async () => {
    take(await generateBrief(companyId, appId, language));
    setConfirming(false);
  });
  const review = () => run(async () => take(await saveBrief(companyId, appId, content)));
  const send = () => run(async () => take(await sendBrief(companyId, appId)));

  const sent = brief?.status === 'sent';
  const reviewed = brief != null && brief.reviewed_by != null && !dirty;
  const statusKey = sent ? 'sent' : reviewed ? 'reviewed' : 'draft';

  return (
    <section aria-labelledby="brief-title" data-testid="brief-workflow" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 id="brief-title" className="text-sm font-extrabold text-slate-950">{t('bridges.brief.title')}</h3>
        {brief && (
          <span data-testid="brief-status" data-status={statusKey} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
            {t(`bridges.brief.status.${statusKey}`)}
          </span>
        )}
      </div>
      <p className="text-xs text-slate-500">{t('bridges.brief.hint')}</p>
      <ErrorAlert message={error} />

      {loaded && !sent && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-bold text-slate-600">
            {t('bridges.brief.language')}
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className={`${inputClass} mt-1 block`}>
              {LANGUAGES.map((code) => <option key={code} value={code}>{t(`bridges.brief.languages.${code}`)}</option>)}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={() => (brief ? setConfirming(true) : generate())} className={brief ? secondaryButton : primaryButton}>
            {brief ? t('bridges.brief.regenerate') : t('bridges.brief.generate')}
          </button>
        </div>
      )}
      {!loaded && !error && <p className="text-xs text-slate-500">{t('common.loading')}</p>}
      {loaded && !sent && <p className="text-xs text-slate-500">{t('bridges.brief.replacesNote')}</p>}
      {confirming && (
        <ConfirmBar message={t('bridges.brief.regenerateConfirm')} confirmLabel={t('bridges.brief.regenerate')} busy={busy} onConfirm={generate} onCancel={() => setConfirming(false)} />
      )}

      {content && (
        <>
          <BriefEditor
            content={content}
            onChange={sent ? undefined : (next) => { setContent(next); setDirty(true); }}
            companyId={companyId}
            appId={appId}
            audioPositions={audioPositions}
          />
          {sent ? (
            <p data-testid="brief-sent" className="text-sm font-bold text-slate-900">{t('bridges.brief.sentNote')}</p>
          ) : (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy || (reviewed && !dirty)} onClick={review} className={secondaryButton}>
                  {t('bridges.brief.markReviewed')}
                </button>
                <button type="button" disabled={busy || !reviewed} onClick={send} className={primaryButton}>
                  {t('bridges.brief.send')}
                </button>
              </div>
              {!reviewed && <p data-testid="send-blocked" className="text-xs font-semibold text-amber-800">{t('bridges.brief.reviewFirst')}</p>}
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default BriefEditor;
