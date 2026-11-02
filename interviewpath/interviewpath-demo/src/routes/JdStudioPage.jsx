import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import AssistantPanel from '../components/jd/AssistantPanel.jsx';
import ChannelContent from '../components/jd/ChannelContent.jsx';
import LineEditor from '../components/jd/LineEditor.jsx';
import LintPanel from '../components/jd/LintPanel.jsx';
import { ErrorAlert, cardClass, inputClass, primaryButton, secondaryButton } from '../components/KbFeedback.jsx';
import {
  acknowledgeUnchecked, approveDraft, askAssistant, confirmDraftLine, dismissProposal, generateChannelContent,
  getChannelContent, getDraft, patchDraftLines, publishDraft, requestDraftChanges, rerunLint, submitDraft,
} from '../lib/bridges.js';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'vi', label: 'Tiếng Việt' },
  { code: 'ko', label: '한국어' },
];

// The approver sends the draft back to HR with what should change.
function RequestChangesForm({ busy, onSend }) {
  const { t } = useTranslation();
  const [comment, setComment] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    if (await onSend(comment.trim())) setComment('');
  };

  return (
    <form onSubmit={submit} className="flex w-full flex-wrap items-end gap-3">
      <label className="min-w-64 flex-1 text-sm font-semibold text-slate-700">
        {t('jd.feedback.comment')}
        <textarea
          rows={2}
          maxLength={2000}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          className={`${inputClass} mt-1 w-full`}
        />
      </label>
      <button type="submit" disabled={busy || !comment.trim()} className={secondaryButton}>
        {t('jd.feedback.send')}
      </button>
    </form>
  );
}

function ManagerFeedback({ items }) {
  const { t } = useTranslation();
  if (items.length === 0) return null;
  return (
    <section aria-label={t('jd.feedback.title')} data-testid="manager-feedback" className={`${cardClass} space-y-2`}>
      <h2 className="text-lg font-extrabold tracking-tight">{t('jd.feedback.title')}</h2>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={`${item.created_at}-${index}`} className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {item.comment}
          </li>
        ))}
      </ul>
    </section>
  );
}

function JdStudio() {
  const { t, i18n } = useTranslation();
  const { draftId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const isHr = membership?.role === 'hr';
  const isManager = membership?.role === 'manager';

  const [draft, setDraft] = useState(null);
  // Until a tab is chosen, the page opens in the interface language: a manager reads the Korean version.
  const [chosenLang, setLang] = useState(null);
  const lang = chosenLang ?? (LANGUAGES.some((l) => l.code === i18n.language) ? i18n.language : 'en');
  const [channels, setChannels] = useState([]);
  const [channelError, setChannelError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getDraft(companyId, draftId)
      .then(async (data) => {
        if (cancelled) return;
        setDraft(data);
        if (data.status === 'published' && isHr) {
          const content = await getChannelContent(companyId, draftId).catch(() => null);
          if (!cancelled && content) setChannels(content.channels);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, draftId, isHr]);

  // Runs one action. `call` returns the new draft (or throws); the result tells the caller whether it worked.
  const act = useCallback(async (call) => {
    setError('');
    setBusy(true);
    try {
      const next = await call();
      setDraft(next);
      return next;
    } catch (err) {
      setError(err.message);
      // The draft moved, so what this page shows is out of date: show what it says now, beside the message.
      if (err.status === 409) {
        const current = await getDraft(companyId, draftId).catch(() => null);
        if (current) setDraft(current);
      }
      return null;
    } finally {
      setBusy(false);
    }
  }, [companyId, draftId]);

  const lineNumbers = useMemo(
    () => Object.fromEntries((draft?.lines ?? []).map((line, index) => [line.id, index + 1])),
    [draft],
  );

  if (loading) return <p className="p-8 text-sm font-semibold text-slate-500">{t('common.loading')}</p>;
  if (!draft) {
    return (
      <div className="space-y-4 p-8">
        <ErrorAlert message={error} />
        <Link to="/hiring-requests" className={secondaryButton}>
          {t('jd.back')}
        </Link>
      </div>
    );
  }

  const status = draft.status;
  const issues = draft.lint ?? [];
  const incomplete = (draft.failed_languages ?? []).length > 0;
  const clean = !draft.blocks_publish && !incomplete && draft.lines.length > 0;
  const canSubmit = isHr && status === 'draft';
  const unsupportedLines = new Set(issues.filter((issue) => issue.check === 'no_source').map((issue) => issue.line_id));

  const saveLine = async (lineId, text) =>
    Boolean(await act(() => patchDraftLines(companyId, draft.id, [{ id: lineId, text: { [lang]: text } }])));
  const removeLine = (lineId) => act(() => patchDraftLines(companyId, draft.id, [{ id: lineId, delete: true }]));
  const confirmLine = (lineId) => act(() => confirmDraftLine(companyId, draft.id, lineId));
  const differentScope = (lineId, nodeId) => {
    const line = draft.lines.find((l) => l.id === lineId);
    const known = line?.conflict_dismissed ?? [];
    return act(() => patchDraftLines(companyId, draft.id, [{ id: lineId, conflict_dismissed: [...new Set([...known, nodeId])] }]));
  };
  const sendMessage = async (message) => Boolean(await act(() => askAssistant(companyId, draft.id, message)));

  const publish = async () => {
    const published = await act(() => publishDraft(companyId, draft.id, draft.version));
    if (!published) return;
    setChannels([]); // the lines changed: text written for the version before must not be shown
    setChannelError('');
    try {
      setChannels((await generateChannelContent(companyId, draft.id)).channels);
    } catch (err) {
      setChannelError(err.message);
    }
  };
  const generateChannels = async () => {
    setChannelError('');
    setBusy(true);
    try {
      setChannels((await generateChannelContent(companyId, draft.id)).channels);
    } catch (err) {
      setChannelError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const hint = (() => {
    if (isHr && status === 'draft' && !clean) return t('jd.hint.blocked');
    return t(`jd.hint.${status}${isManager ? 'Manager' : ''}`, { defaultValue: '' });
  })();

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-extrabold tracking-tight">{t('jd.title')}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <span data-testid="draft-status" className="rounded-full bg-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-slate-700">
            {t(`jd.status.${status}`, { defaultValue: status })}
          </span>
          <span data-testid="draft-version" data-version={draft.version} className="text-xs font-bold text-slate-500">
            {t('jd.version', { version: draft.version })}
          </span>
        </div>
      </div>
      <ErrorAlert message={error} />

      <section data-testid="status-bar" className={`${cardClass} flex flex-wrap items-center gap-3`}>
        <p className="min-w-64 flex-1 text-sm font-semibold text-slate-700">{hint}</p>
        {isHr && (
          <>
            {canSubmit && (
              <button type="button" disabled={busy || !clean} onClick={() => act(() => submitDraft(companyId, draft.id))} className={secondaryButton}>
                {t('jd.submit')}
              </button>
            )}
            <button type="button" disabled={busy || status !== 'approved' || !clean} onClick={publish} className={primaryButton}>
              {t('jd.publish')}
            </button>
          </>
        )}
        {isManager && status === 'manager_review' && (
          <>
            <button type="button" disabled={busy} onClick={() => act(() => approveDraft(companyId, draft.id, draft.version))} className={primaryButton}>
              {t('jd.approve')}
            </button>
            <RequestChangesForm busy={busy} onSend={(comment) => act(() => requestDraftChanges(companyId, draft.id, comment))} />
          </>
        )}
      </section>

      <ManagerFeedback items={draft.manager_feedback ?? []} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-label={t('jd.lines')} className="space-y-3">
          <div role="tablist" aria-label={t('jd.languageTabs')} className="flex gap-2">
            {LANGUAGES.map((item) => (
              <button
                key={item.code}
                role="tab"
                type="button"
                aria-selected={lang === item.code}
                onClick={() => setLang(item.code)}
                className={`rounded-xl px-3 py-2 text-sm font-bold ${lang === item.code ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 shadow-card'}`}
              >
                {item.label}
              </button>
            ))}
          </div>
          {incomplete && (
            <p role="note" className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
              {t('jd.incomplete', { languages: draft.failed_languages.join(', ') })}
            </p>
          )}
          {(draft.rejected ?? []).length > 0 && (
            <div role="note" data-testid="rejected-lines" className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <p className="font-semibold">{t('jd.rejected', { count: draft.rejected.length })}</p>
              <ul className="space-y-1">
                {draft.rejected.map((item) => (
                  <li key={item.line_id} data-testid="rejected-line">
                    <span className="font-semibold">{item.text?.[lang] || item.text?.en || item.text?.vi || item.text?.ko}</span>
                    {' · '}
                    {t(`jd.rejectedReasons.${item.code}`, { defaultValue: t('jd.rejectedReasons.unknown'), numbers: (item.detail ?? []).join(', ') })}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {draft.lines.length === 0 && <p className={`${cardClass} text-sm font-semibold text-slate-600`}>{t('jd.noLines')}</p>}
          <ol data-testid="jd-lines" className="space-y-2">
            {draft.lines.map((line, index) => (
              <LineEditor
                key={line.id}
                line={line}
                number={index + 1}
                lang={lang}
                canEdit={isHr}
                busy={busy}
                unsupported={unsupportedLines.has(line.id)}
                onSave={saveLine}
                onRemove={removeLine}
                onConfirm={confirmLine}
                onFlag={(lineId, flags) => act(() => patchDraftLines(companyId, draft.id, [{ id: lineId, ...flags }]))}
              />
            ))}
          </ol>
        </section>

        <div className="space-y-6">
          {isHr && (
            <AssistantPanel
              messages={draft.messages ?? []}
              proposals={draft.proposals ?? []}
              busy={busy}
              onSend={sendMessage}
              onConfirm={confirmLine}
              onDismiss={(id) => act(() => dismissProposal(companyId, draft.id, id))}
            />
          )}
          <LintPanel
            issues={issues}
            lineNumbers={lineNumbers}
            canAct={isHr}
            busy={busy}
            onDifferentScope={differentScope}
            onRerun={() => act(() => rerunLint(companyId, draft.id))}
            onAcknowledge={(lineId) => act(() => acknowledgeUnchecked(companyId, draft.id, lineId))}
          />
        </div>
      </div>

      {isHr && status === 'published' && (
        <ChannelContent channels={channels} busy={busy} error={channelError} onGenerate={generateChannels} />
      )}
    </div>
  );
}

// The key remounts the page when the draft changes.
function JdStudioPage() {
  const { draftId } = useParams();
  return <JdStudio key={draftId} />;
}

export default JdStudioPage;
