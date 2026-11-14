import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import BoardCell from '../components/board/BoardCell.jsx';
import CandidateCard from '../components/CandidateCard.jsx';
import CandidateDetailPanel from '../components/CandidateDetailPanel.jsx';
import { ErrorAlert } from '../components/KbFeedback.jsx';
import FeedbackQueue from '../components/board/FeedbackQueue.jsx';
import TalentMatches from '../components/board/TalentMatches.jsx';
import { LANES, bulkReject, getBoard, importCvs } from '../lib/board.js';
import { listFeedback } from '../lib/posthire.js';

const IMPORT_CHANNELS = ['topcv', 'itviec', 'linkedin', 'referral', 'direct'];

function BoardPage() {
  const { t } = useTranslation();
  const { jobId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [board, setBoard] = useState(null);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [importChannel, setImportChannel] = useState('topcv');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const reload = useCallback(async () => {
    const [data, waiting] = await Promise.all([getBoard(companyId, jobId), listFeedback(companyId, jobId, 'draft')]);
    setBoard(data);
    setDrafts(waiting);
  }, [companyId, jobId]);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    Promise.all([getBoard(companyId, jobId), listFeedback(companyId, jobId, 'draft')])
      .then(([data, waiting]) => { if (!cancelled) { setBoard(data); setDrafts(waiting); } })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [companyId, jobId]);

  const waiting = new Set(drafts.map((draft) => draft.application_id));
  const pendingIn = (cell) => board.cells[cell].filter((card) => waiting.has(card.id)).length;

  const rejectMany = async (ids) => {
    setError('');
    try {
      await bulkReject(companyId, jobId, ids);
      await reload();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleBulkImport = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setImporting(true);
    setError('');
    setImportResult(null);
    try {
      const res = await importCvs(companyId, jobId, importChannel, files);
      setImportResult(res);
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  const totalMatrixCount = board
    ? Object.values(board.cells).reduce((acc, list) => acc + (list?.length ?? 0), 0)
    : 0;
  const hiddenGemCount = board?.cells?.hidden_gem?.length ?? 0;
  const holdCount = board?.lanes?.cv_hold?.length ?? 0;
  const inProgressCount = board?.lanes?.in_progress?.length ?? 0;

  return (
    <div className="mx-auto max-w-[1440px] space-y-8 px-8 py-7">
      <header className="border-b border-slate-200/90 pb-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2.5 text-xs font-semibold text-slate-600">
              <span className="inline-block h-2 w-2 rounded-full bg-blue-700" aria-hidden="true" />
              <span>{t('board.eyebrow')}</span>
              <span className="text-slate-300" aria-hidden="true">/</span>
              <span className="font-medium text-slate-500">2×2 calibration matrix</span>
            </div>
            <h1 className="mt-2 text-[1.75rem] font-extrabold leading-tight tracking-[-0.025em] text-slate-950">
              {board?.job?.title ?? t('board.title')}
            </h1>
            <p className="mt-1.5 max-w-[68ch] text-sm leading-relaxed text-slate-600">{t('board.intro')}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {board && (
              <dl className="hidden items-center divide-x divide-slate-200 rounded-xl border border-slate-200/90 bg-white px-2 py-2 sm:flex">
                <div className="px-3.5">
                  <dt className="text-[11px] font-medium text-slate-500">Scored interviews</dt>
                  <dd className="mt-0.5 text-base font-extrabold tabular-nums text-slate-950">{totalMatrixCount}</dd>
                </div>
                <div className="px-3.5">
                  <dt className="text-[11px] font-medium text-violet-800">Hidden gems</dt>
                  <dd className="mt-0.5 text-base font-extrabold tabular-nums text-violet-700">{hiddenGemCount}</dd>
                </div>
                <div className="px-3.5">
                  <dt className="text-[11px] font-medium text-amber-800">CV on hold</dt>
                  <dd className="mt-0.5 text-base font-extrabold tabular-nums text-amber-700">{holdCount}</dd>
                </div>
                <div className="px-3.5">
                  <dt className="text-[11px] font-medium text-slate-500">In interview</dt>
                  <dd className="mt-0.5 text-base font-extrabold tabular-nums text-slate-900">{inProgressCount}</dd>
                </div>
              </dl>
            )}

            <div className="flex items-center gap-2 rounded-xl border border-slate-200/90 bg-white p-1.5 shadow-sm">
              <select
                value={importChannel}
                onChange={(e) => setImportChannel(e.target.value)}
                aria-label={t('board.import.channel', { defaultValue: 'Source channel' })}
                className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-blue-600 focus:outline-none"
              >
                {IMPORT_CHANNELS.map((ch) => (
                  <option key={ch} value={ch}>{ch.toUpperCase()}</option>
                ))}
              </select>
              <label className="cursor-pointer rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-700">
                {importing
                  ? t('common.loading')
                  : t('board.import.button', { defaultValue: 'Import CVs (.pdf / .docx / .zip)' })}
                <input
                  type="file"
                  multiple
                  accept=".pdf,.docx,.zip"
                  disabled={importing}
                  onChange={handleBulkImport}
                  className="sr-only"
                />
              </label>
            </div>
          </div>
        </div>
      </header>
      {importResult && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-semibold text-emerald-900">
          {t('board.import.summary', {
            imported: importResult.imported,
            duplicates: importResult.duplicates,
            missing: importResult.missing_contact,
            defaultValue: `Imported ${importResult.imported} CV(s), ${importResult.duplicates} duplicate(s) merged, ${importResult.missing_contact} missing contact.`,
          })}
        </p>
      )}
      <ErrorAlert message={error} />
      {!board && !error && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {board && (
        <>
          <div className="overflow-hidden rounded-2xl border border-slate-300/90 bg-slate-200/60 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-900 px-5 py-3 text-white">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold tracking-tight">Evidence calibration matrix</span>
                <span className="text-xs text-slate-300">Cross-referencing paper CV screening against spoken Round 1 interview evidence</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-300">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden="true" />
                  High spoken evidence
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-violet-400" aria-hidden="true" />
                  Hidden Gem quadrant
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[2.75rem_1fr_1fr]">
              <span className="hidden border-b border-r border-slate-200/90 bg-slate-100/90 lg:block" />
              <div className="border-b border-slate-200/90 bg-slate-100/90 px-5 py-2.5 lg:border-r">
                <p className="text-xs font-bold text-slate-800">{t('board.axes.much')}</p>
              </div>
              <div className="border-b border-slate-200/90 bg-slate-100/90 px-5 py-2.5">
                <p className="text-xs font-bold text-slate-600">{t('board.axes.little')}</p>
              </div>

              <div className="hidden items-center justify-center border-b border-r border-slate-200/90 bg-slate-100/90 px-2 lg:flex">
                <p className="text-xs font-bold text-slate-700 [writing-mode:vertical-rl] rotate-180">{t('board.axes.meets')}</p>
              </div>
              <div className="border-b border-slate-200/90 bg-white lg:border-r">
                <BoardCell cellKey="priority" cards={board.cells.priority} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} feedbackPending={pendingIn('priority')} />
              </div>
              <div className="border-b border-slate-200/90 bg-white">
                <BoardCell cellKey="strong_cv_unclear" cards={board.cells.strong_cv_unclear} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} feedbackPending={pendingIn('strong_cv_unclear')} />
              </div>

              <div className="hidden items-center justify-center border-r border-slate-200/90 bg-slate-100/90 px-2 lg:flex">
                <p className="text-xs font-bold text-slate-600 [writing-mode:vertical-rl] rotate-180">{t('board.axes.notMet')}</p>
              </div>
              <div className="border-b border-slate-200/90 bg-white lg:border-b-0 lg:border-r">
                <BoardCell cellKey="hidden_gem" cards={board.cells.hidden_gem} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} feedbackPending={pendingIn('hidden_gem')} />
              </div>
              <div className="bg-white">
                <BoardCell cellKey="not_enough_evidence" cards={board.cells.not_enough_evidence} selectedId={selectedId} onSelect={setSelectedId} onBulkReject={rejectMany} feedbackPending={pendingIn('not_enough_evidence')} />
              </div>
            </div>
          </div>

          <FeedbackQueue companyId={companyId} drafts={drafts} onOpen={setSelectedId} onChanged={reload} />
          <TalentMatches companyId={companyId} jobId={jobId} onInvited={reload} />

          <section aria-label={t('board.lanes.title')} className="space-y-4 pt-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 pb-2.5">
              <h2 className="text-base font-extrabold tracking-tight text-slate-950">{t('board.lanes.title')}</h2>
              <p className="text-xs text-slate-500">Pre-matrix stages: resumes held at screening, active voice sessions, or exceptions</p>
            </div>
            <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-3">
              {[...LANES]
                .sort((a, b) => ((board.lanes[b]?.length ?? 0) > 0 ? 1 : 0) - ((board.lanes[a]?.length ?? 0) > 0 ? 1 : 0))
                .map((lane) => {
                  const items = board.lanes[lane] ?? [];
                  const hasItems = items.length > 0;
                  const isHold = lane === 'cv_hold';
                  return (
                    <div
                      key={lane}
                      data-testid={`lane-${lane}`}
                      className={[
                        'flex flex-col rounded-xl border transition-colors',
                        hasItems
                          ? isHold
                            ? 'border-amber-300 bg-amber-50/25 p-4 shadow-sm'
                            : 'border-slate-200/90 bg-white p-4 shadow-sm'
                          : 'border-slate-200/60 bg-slate-50/70 px-4 py-3',
                      ].join(' ')}
                    >
                      <div className={`flex items-center justify-between gap-2 ${hasItems ? 'border-b border-slate-100 pb-3' : ''}`}>
                        <div className="flex items-center gap-2">
                          <span
                            className={[
                              'h-2 w-2 rounded-full',
                              !hasItems ? 'bg-slate-300' : isHold ? 'bg-amber-500' : 'bg-blue-600',
                            ].join(' ')}
                            aria-hidden="true"
                          />
                          <h3 className={`text-sm ${hasItems ? 'font-bold text-slate-950' : 'font-medium text-slate-500'}`}>
                            {t(`board.lanes.${lane}`)}
                          </h3>
                        </div>
                        <span
                          data-testid={`count-${lane}`}
                          className={[
                            'rounded-md px-2 py-0.5 text-xs font-bold tabular-nums',
                            !hasItems
                              ? 'bg-slate-200/70 text-slate-500'
                              : isHold
                                ? 'bg-amber-100 text-amber-900'
                                : 'bg-slate-900 text-white',
                          ].join(' ')}
                        >
                          {items.length}
                        </span>
                      </div>
                      {hasItems && (
                        <div className="mt-3 space-y-2.5">
                          {items.map((card) => (
                            <CandidateCard key={card.id} card={card} selected={card.id === selectedId} onClick={() => setSelectedId(card.id)} />
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </section>
        </>
      )}

      {selectedId != null && (
        <CandidateDetailPanel key={selectedId} companyId={companyId} appId={selectedId} onClose={() => setSelectedId(null)} onChanged={reload} />
      )}
    </div>
  );
}

export default BoardPage;
