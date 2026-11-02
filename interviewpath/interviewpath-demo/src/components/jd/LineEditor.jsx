import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { inputClass, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// One line of the description in the chosen language: its source chips, an inline edit, and a mark when nothing in the
// knowledge graph supports it. `titles` maps node ids to titles; a manager has none, so a chip then names the node id.
function LineEditor({ line, number, lang, titles, canEdit, busy, onSave, onRemove, onConfirm, onFlag }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const text = line.text?.[lang] ?? '';
  const sources = line.source_node_ids ?? [];
  const unsourced = sources.length === 0 && !line.hr_confirmed;

  const start = () => {
    setValue(text);
    setEditing(true);
  };
  const save = async () => {
    if (await onSave(line.id, value.trim())) setEditing(false);
  };

  return (
    <li
      data-testid={`jd-line-${line.id}`}
      data-unsourced={unsourced ? 'true' : 'false'}
      className="space-y-2 rounded-xl border border-slate-200 bg-white p-3"
    >
      {editing ? (
        <div className="space-y-2">
          <textarea
            aria-label={t('jd.lineText', { number })}
            rows={2}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className={`${inputClass} w-full`}
          />
          <div className="flex gap-2">
            <button type="button" disabled={busy || !value.trim()} onClick={save} className={primaryButton}>
              {t('common.save')}
            </button>
            <button type="button" disabled={busy} onClick={() => setEditing(false)} className={secondaryButton}>
              {t('common.cancel')}
            </button>
          </div>
        </div>
      ) : (
        <p data-testid="jd-line-text" lang={lang} className="text-sm text-slate-900">
          {text || <span className="italic text-slate-400">{t('jd.emptyInLanguage')}</span>}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {sources.map((id) => (
          <span key={id} data-testid="source-chip" className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-800">
            {titles?.[id] ?? t('jd.sourceNode', { id })}
          </span>
        ))}
        {unsourced && (
          <span data-testid="unsourced-mark" className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-800">
            {t('jd.unsourced')}
          </span>
        )}
        {line.hr_confirmed && (
          <span data-testid="confirmed-label" className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-800">
            {t('jd.confirmedByHr')}
          </span>
        )}
        {!canEdit && line.is_requirement && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
            {line.must_have ? t('jd.mustHave') : t('jd.requirement')}
          </span>
        )}
      </div>

      {canEdit && (
        <div className="flex flex-wrap gap-4 text-xs font-semibold text-slate-700">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              aria-label={t('jd.isRequirementLine', { number })}
              checked={Boolean(line.is_requirement)}
              disabled={busy}
              onChange={(e) => onFlag(line.id, { is_requirement: e.target.checked })}
            />
            {t('jd.requirement')}
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              aria-label={t('jd.isMustHaveLine', { number })}
              checked={Boolean(line.must_have)}
              disabled={busy || !line.is_requirement}
              onChange={(e) => onFlag(line.id, { must_have: e.target.checked })}
            />
            {t('jd.mustHave')}
          </label>
        </div>
      )}

      {canEdit && !editing && (
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={busy} aria-label={t('jd.editLine', { number })} onClick={start} className={secondaryButton}>
            {t('jd.edit')}
          </button>
          {unsourced && (
            <button type="button" disabled={busy} aria-label={t('jd.confirmLine', { number })} onClick={() => onConfirm(line.id)} className={secondaryButton}>
              {t('jd.confirmLineShort')}
            </button>
          )}
          <button type="button" disabled={busy} aria-label={t('jd.removeLine', { number })} onClick={() => onRemove(line.id)} className={secondaryButton}>
            {t('common.remove')}
          </button>
        </div>
      )}
    </li>
  );
}

export default LineEditor;
