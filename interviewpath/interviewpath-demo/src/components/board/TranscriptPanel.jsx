import { Play } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchTurnAudio } from '../../lib/board.js';

// Audio is fetched only when HR asks for it. Each play is logged by the server.
export function PlayFromMoment({ companyId, appId, position, label }) {
  const { t } = useTranslation();
  const [url, setUrl] = useState(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => () => url && URL.revokeObjectURL(url), [url]);

  const play = async () => {
    setLoading(true);
    setError(false);
    try {
      setUrl(await fetchTurnAudio(companyId, appId, position));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <span className="inline-flex flex-col gap-1">
      {!url && (
        <button
          type="button"
          onClick={play}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-bold text-slate-800 hover:bg-slate-50 disabled:opacity-60"
        >
          <Play size={13} aria-hidden="true" />
          {label ?? t('board.audio.play')}
        </button>
      )}
      {url && <audio controls autoPlay src={url} aria-label={t('board.audio.player', { position })} className="h-9" />}
      {error && <span role="alert" className="text-xs font-semibold text-red-700">{t('board.audio.failed')}</span>}
    </span>
  );
}

// The transcript is the first thing HR reads.
function TranscriptPanel({ companyId, appId, turns }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="transcript-title" data-testid="transcript">
      <h3 id="transcript-title" className="text-sm font-extrabold text-slate-950">{t('board.transcript.title')}</h3>
      {turns.length === 0 && <p className="mt-2 text-sm text-slate-500">{t('board.transcript.empty')}</p>}
      <ol className="mt-3 space-y-3">
        {turns.map((turn) => (
          <li key={turn.position} id={`turn-${turn.position}`} className="rounded-xl bg-slate-50 p-3">
            <p className="text-xs font-bold text-slate-500">
              {turn.is_followup ? t('board.transcript.followup') : t('board.transcript.question')} {turn.position}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{turn.question}</p>
            {turn.transcript_status === 'transcribed' && turn.transcript ? (
              <p className="mt-2 text-sm text-slate-700">{turn.transcript}</p>
            ) : (
              <p className="mt-2 text-sm italic text-slate-500">{t('board.transcript.unavailable')}</p>
            )}
            {turn.has_audio && (
              <div className="mt-2">
                <PlayFromMoment companyId={companyId} appId={appId} position={turn.position} />
              </div>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

export default TranscriptPanel;
