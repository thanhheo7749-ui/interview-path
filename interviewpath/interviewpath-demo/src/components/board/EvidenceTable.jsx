import { useTranslation } from 'react-i18next';
import { PlayFromMoment } from './TranscriptPanel.jsx';

function Quote({ text }) {
  return text ? <blockquote className="mt-1 border-l-2 border-slate-300 pl-2 text-xs text-slate-600">{text}</blockquote> : null;
}

function Cited({ companyId, appId, evidence, audioPositions, statusPrefix }) {
  const { t } = useTranslation();
  if (!evidence) return <span className="text-xs text-slate-400">{t('board.evidence.noResult')}</span>;
  const position = evidence.position;
  return (
    <div>
      <p className="text-xs font-bold text-slate-800">{t(`board.${statusPrefix}.${evidence.status}`, { defaultValue: evidence.status })}</p>
      <Quote text={evidence.quote} />
      {position != null && audioPositions.has(position) && (
        <div className="mt-1">
          <PlayFromMoment companyId={companyId} appId={appId} position={position} />
        </div>
      )}
    </div>
  );
}

// CV and interview evidence side by side. There is no total and no score.
function EvidenceTable({ companyId, appId, requirements, claims, cultureNotes, turns }) {
  const { t } = useTranslation();
  const audioPositions = new Set(turns.filter((turn) => turn.has_audio).map((turn) => turn.position));

  return (
    <div className="space-y-6">
      <section aria-labelledby="req-title">
        <h3 id="req-title" className="text-sm font-extrabold text-slate-950">{t('board.evidence.title')}</h3>
        <div className="mt-2 overflow-x-auto">
          <table data-testid="evidence-table" className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
                <th className="py-2 pr-3">{t('board.evidence.requirement')}</th>
                <th className="py-2 pr-3">{t('board.evidence.cv')}</th>
                <th className="py-2">{t('board.evidence.interview')}</th>
              </tr>
            </thead>
            <tbody>
              {requirements.map((req) => (
                <tr key={req.requirement_id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pr-3">
                    <p className="font-semibold text-slate-900">{req.text}</p>
                    <p className="mt-1 flex flex-wrap gap-1.5">
                      {req.must_have && <span className="rounded-full bg-slate-950 px-2 py-0.5 text-[11px] font-bold text-white">{t('board.evidence.mustHave')}</span>}
                      {req.visibility === 'confidential' && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800">{t('board.evidence.confidential')}</span>
                      )}
                    </p>
                  </td>
                  <td className="py-2 pr-3">
                    <Cited companyId={companyId} appId={appId} evidence={req.cv} audioPositions={audioPositions} statusPrefix="evidence.status" />
                  </td>
                  <td className="py-2">
                    <Cited companyId={companyId} appId={appId} evidence={req.interview} audioPositions={audioPositions} statusPrefix="evidence.status" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="claims-title" data-testid="claims">
        <h3 id="claims-title" className="text-sm font-extrabold text-slate-950">{t('board.claims.title')}</h3>
        {claims.length === 0 && <p className="mt-2 text-sm text-slate-500">{t('board.claims.empty')}</p>}
        <ul className="mt-2 space-y-3">
          {claims.map((claim) => (
            <li key={claim.id} className="rounded-xl bg-slate-50 p-3">
              <p className="text-sm font-semibold text-slate-900">{claim.text}</p>
              <p className="mt-1 text-xs font-bold text-slate-600">{t(`board.claims.status.${claim.status}`, { defaultValue: claim.status ?? '' })}</p>
              <Quote text={claim.evidence_quote} />
              {claim.position != null && audioPositions.has(claim.position) && (
                <div className="mt-1">
                  <PlayFromMoment companyId={companyId} appId={appId} position={claim.position} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="culture-title" data-testid="culture-notes">
        <h3 id="culture-title" className="text-sm font-extrabold text-slate-950">{t('board.culture.title')}</h3>
        <p className="mt-1 text-xs text-slate-500">{t('board.culture.hint')}</p>
        {cultureNotes.length === 0 && <p className="mt-2 text-sm text-slate-500">{t('board.culture.empty')}</p>}
        <ul className="mt-2 space-y-3">
          {cultureNotes.map((note, index) => (
            <li key={`${note.value}-${index}`} className="rounded-xl bg-slate-50 p-3">
              <p className="text-sm font-bold text-slate-900">{note.value}</p>
              <p className="mt-1 text-sm text-slate-700">{note.note}</p>
              <Quote text={note.quote} />
              {note.position != null && audioPositions.has(note.position) && (
                <div className="mt-1">
                  <PlayFromMoment companyId={companyId} appId={appId} position={note.position} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default EvidenceTable;
