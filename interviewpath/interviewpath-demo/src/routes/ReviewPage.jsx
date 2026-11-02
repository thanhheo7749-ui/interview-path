import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';
import {
  ConfirmBar, EmptyState, ErrorAlert, WarningList, cardClass, inputClass, primaryButton, secondaryButton,
} from '../components/KbFeedback.jsx';
import { decideReview, getReviewQueue, notifyKbChanged, uniqueSources } from '../lib/kb.js';

const VISIBILITIES = ['public', 'internal', 'confidential'];

const isFact = (node) => Boolean(node.fact_kind) && node.fact_kind !== 'none';

// The discrimination guard. A flagged item can only be rejected or rewritten; one the check could not look at
// ("unchecked") can be accepted after HR confirms that they read it.
const UNCHECKED = 'unchecked';
const isHeld = (node) => Boolean(node.guard_category);
const isUnchecked = (node) => node.guard_category === UNCHECKED;

function groupByDocument(nodes) {
  const groups = new Map();
  for (const node of nodes) {
    const name = node.sources?.[0]?.document_title ?? '';
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(node);
  }
  return [...groups.entries()].map(([name, items]) => ({ name, items }));
}

function ReviewPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [queue, setQueue] = useState(null);
  const [edits, setEdits] = useState({});
  const [error, setError] = useState('');
  const [warnings, setWarnings] = useState([]);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(null);

  const load = useCallback(async () => {
    const data = await getReviewQueue(companyId);
    setQueue(data);
    setEdits({});
  }, [companyId]);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getReviewQueue(companyId)
      .then((data) => {
        if (!cancelled) setQueue(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const valueOf = (node, field) => edits[node.id]?.[field] ?? node[field];
  const edit = (node, field, value) => setEdits((current) => ({ ...current, [node.id]: { ...current[node.id], [field]: value } }));

  const decide = async (items) => {
    setError('');
    setBusy(true);
    try {
      const result = await decideReview(companyId, items);
      setWarnings(result?.warnings ?? []);
      await load();
      notifyKbChanged();
    } catch (err) {
      setError(err.message);
      // The check could not run on the text HR rewrote: it goes out only once HR confirms having read it.
      if (err.code === UNCHECKED && items.length === 1) setConfirming(items[0].node_id);
    } finally {
      setBusy(false);
    }
  };

  const rewritten = (node) => valueOf(node, 'title') !== node.title || valueOf(node, 'body') !== node.body;
  // A flagged item stays blocked until its text is rewritten; the server checks the new text again.
  const blocked = (node) => isHeld(node) && !isUnchecked(node) && !rewritten(node);

  const accept = (node, confirmUnchecked = false) => ({
    action: 'accept',
    ...(confirmUnchecked ? { confirm_unchecked: true } : {}),
    node_id: node.id,
    title: valueOf(node, 'title'),
    body: valueOf(node, 'body'),
    visibility: valueOf(node, 'visibility'),
    ...(isFact(node)
      ? { fact_value: valueOf(node, 'fact_value'), fact_unit: valueOf(node, 'fact_unit'), scope_text: valueOf(node, 'scope_text') }
      : {}),
  });

  const nodes = queue?.nodes ?? [];
  const proposals = queue?.merge_proposals ?? [];

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('review.title')}</h1>
      <ErrorAlert message={error} />
      <WarningList warnings={warnings} onDismiss={() => setWarnings([])} />

      {queue && nodes.length === 0 && <EmptyState>{t('review.empty')}</EmptyState>}

      {groupByDocument(nodes).map((group) => (
        <section key={group.name} className={`${cardClass} space-y-4`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-extrabold tracking-tight">{group.name || t('review.unknownDocument')}</h2>
            <button type="button" disabled={busy || group.items.every(isHeld)} onClick={() => decide(group.items.filter((node) => !isHeld(node)).map((node) => accept(node)))} className={primaryButton}>
              {t('review.acceptAll')}
            </button>
          </div>

          {group.items.map((node) => {
            const proposal = proposals.find((p) => p.node_id === node.id);
            return (
              <article key={node.id} className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">
                  {t(`review.types.${node.type}`, { defaultValue: node.type })}
                </p>
                {node.review_reason && (
                  <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-900">
                    {t(`review.reasons.${node.review_reason}`, { defaultValue: node.review_reason })}
                  </p>
                )}
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="text-sm font-semibold text-slate-700">
                    <span className="block">{t('review.itemTitle')}</span>
                    <input
                      value={valueOf(node, 'title')}
                      onChange={(e) => edit(node, 'title', e.target.value)}
                      className={`${inputClass} mt-1 w-full`}
                    />
                  </label>
                  <label className="text-sm font-semibold text-slate-700">
                    <span className="block">{t('review.layer')}</span>
                    <select
                      value={valueOf(node, 'visibility')}
                      onChange={(e) => edit(node, 'visibility', e.target.value)}
                      className={`${inputClass} mt-1 w-full`}
                    >
                      {VISIBILITIES.map((v) => (
                        <option key={v} value={v}>
                          {t(`layers.${v}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="block text-sm font-semibold text-slate-700">
                  <span className="block">{t('review.body')}</span>
                  <textarea
                    rows={3}
                    value={valueOf(node, 'body')}
                    onChange={(e) => edit(node, 'body', e.target.value)}
                    className={`${inputClass} mt-1 w-full`}
                  />
                </label>
                {isFact(node) && (
                  <div className="grid gap-3 md:grid-cols-3">
                    <label className="text-sm font-semibold text-slate-700">
                      <span className="block">{t('review.factValue')}</span>
                      <input
                        maxLength={255}
                        value={valueOf(node, 'fact_value') ?? ''}
                        onChange={(e) => edit(node, 'fact_value', e.target.value)}
                        className={`${inputClass} mt-1 w-full`}
                      />
                    </label>
                    <label className="text-sm font-semibold text-slate-700">
                      <span className="block">{t('review.factUnit')}</span>
                      <input
                        maxLength={50}
                        value={valueOf(node, 'fact_unit') ?? ''}
                        onChange={(e) => edit(node, 'fact_unit', e.target.value)}
                        className={`${inputClass} mt-1 w-full`}
                      />
                    </label>
                    <label className="text-sm font-semibold text-slate-700">
                      <span className="block">{t('review.factScope')}</span>
                      <input
                        maxLength={500}
                        value={valueOf(node, 'scope_text') ?? ''}
                        onChange={(e) => edit(node, 'scope_text', e.target.value)}
                        className={`${inputClass} mt-1 w-full`}
                      />
                    </label>
                  </div>
                )}
                {uniqueSources(node.sources).map((source) => (
                  <blockquote key={`${source.document_title}-${source.page}-${source.quote}`} className="border-l-4 border-blue-300 pl-3 text-sm text-slate-700">
                    <p>{source.quote}</p>
                    <footer className="mt-1 text-xs text-slate-500">
                      {source.document_title}
                      {source.page != null ? `, ${t('review.page', { page: source.page })}` : ''}
                      {source.effective_date ? `, ${t('review.effective', { date: source.effective_date })}` : ''}
                    </footer>
                  </blockquote>
                ))}
                {isHeld(node) && (
                  <div
                    role="note"
                    data-testid={isUnchecked(node) ? 'guard-unchecked' : 'guard-flagged'}
                    className={`space-y-1 rounded-xl border px-3 py-2 text-sm ${isUnchecked(node) ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-red-200 bg-red-50 text-red-900'}`}
                  >
                    <p className="font-bold">
                      {isUnchecked(node)
                        ? t('review.guard.uncheckedTitle')
                        : t('review.guard.flaggedTitle', { category: t(`review.guard.categories.${node.guard_category}`, { defaultValue: node.guard_category }) })}
                    </p>
                    <p data-testid="guard-reason">{node.guard_reason}</p>
                    <p>{isUnchecked(node) ? t('review.guard.uncheckedHint') : t('review.guard.flaggedHint')}</p>
                  </div>
                )}
                {proposal && (
                  <div className="flex flex-wrap items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
                    <p>
                      {t('review.mergeHint', { title: proposal.into_title, percent: Math.round(proposal.cosine * 100) })}
                    </p>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => decide([{ action: 'merge', node_id: node.id, into_node_id: proposal.into_node_id }])}
                      className={secondaryButton}
                    >
                      {t('review.merge')}
                    </button>
                  </div>
                )}
                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled={busy || blocked(node)}
                    onClick={() => (isUnchecked(node) && !rewritten(node) ? setConfirming(node.id) : decide([accept(node)]))}
                    className={primaryButton}
                  >
                    {t('review.accept')}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => decide([{ action: 'reject', node_id: node.id }])}
                    className={secondaryButton}
                  >
                    {t('review.reject')}
                  </button>
                </div>
                {confirming === node.id && (
                  <ConfirmBar
                    message={t('review.guard.confirmMessage')}
                    confirmLabel={t('review.guard.confirm')}
                    busy={busy}
                    onConfirm={async () => {
                      await decide([accept(node, true)]);
                      setConfirming(null);
                    }}
                    onCancel={() => setConfirming(null)}
                  />
                )}
              </article>
            );
          })}
        </section>
      ))}
    </div>
  );
}

export default ReviewPage;
