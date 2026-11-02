import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MAX_ANSWER_SECONDS, useAnswerRecorder } from '../../hooks/useAnswerRecorder.js';
import { fetchQuestionAudio, getVoiceState, submitVoiceAnswer } from '../../lib/bridges.js';

const ACTIVE = ['in_progress', 'closing', 'paused'];

const formatClock = (seconds) => {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

export const stopStream = (stream) => stream?.getTracks().forEach((track) => track.stop());

// Opens the microphone and shows its level, so the speaker can hear it works before anything is recorded.
export function MicCheck({ onStream }) {
  const { t } = useTranslation();
  const [level, setLevel] = useState(null);
  const [error, setError] = useState(false);
  const cleanupRef = useRef(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const test = async () => {
    setError(false);
    cleanupRef.current?.();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const context = new window.AudioContext();
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      context.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      let frame = 0;
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        const peak = data.reduce((max, value) => Math.max(max, Math.abs(value - 128)), 0);
        setLevel(Math.min(100, Math.round((peak / 128) * 100)));
        frame = requestAnimationFrame(tick);
      };
      tick();
      cleanupRef.current = () => {
        cancelAnimationFrame(frame);
        context.close().catch(() => undefined);
      };
      onStream(stream);
    } catch {
      setLevel(null);
      setError(true);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 className="font-bold">{t('bridges.voice.micTitle')}</h2>
      <p className="mt-1 text-sm text-slate-600">{t('bridges.voice.micHint')}</p>
      <button
        type="button"
        onClick={test}
        className="mt-3 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-800 shadow-card hover:bg-slate-50"
      >
        {t('bridges.voice.micTest')}
      </button>
      {level !== null && (
        <div data-testid="mic-level" className="mt-3 h-3 w-full overflow-hidden rounded-full bg-slate-200" aria-label={t('bridges.voice.micLevel')}>
          <div className="h-full bg-blue-600 transition-all" style={{ width: `${level}%` }} />
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm font-semibold text-red-700">
          {t('bridges.voice.micError')}
        </p>
      )}
    </section>
  );
}

// The portal's room for a spoken session over /api/voice: question text and audio, a recording indicator, progress
// and time left. The microphone stream comes from the caller's mic check. The room releases it when the session ends;
// the caller releases it when the page is left.
function VoiceRoom({ initialState, stream, completedMessage, onFinished }) {
  const { t } = useTranslation();
  const [session, setSession] = useState(initialState);
  const [remaining, setRemaining] = useState(initialState.time_left_seconds);
  const [uploading, setUploading] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const pendingRef = useRef(null);
  const sessionRef = useRef(initialState);
  const audioRef = useRef(null);
  const streamRef = useRef(stream);

  useEffect(() => {
    streamRef.current = stream;
  }, [stream]);

  // Stop anything playing when the room goes away. The microphone stream belongs to the page that opened it, which
  // releases it on unmount; stopping it here would also fire on React's development remount and kill the recording.
  useEffect(
    () => () => {
      audioRef.current?.pause();
      audioRef.current = null;
    },
    [],
  );

  const applyState = useCallback(
    (next) => {
      sessionRef.current = next;
      setSession(next);
      setRemaining(next.time_left_seconds);
      setUploadFailed(false);
      pendingRef.current = null;
      if (!ACTIVE.includes(next.status)) {
        stopStream(streamRef.current);
        onFinished?.(next);
      }
    },
    [onFinished],
  );

  useEffect(() => {
    const timer = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(timer);
  }, []);

  // Send one answer. If the connection drops, ask the server where we are before offering a resend: the answer may
  // have been stored even though the reply was lost.
  const send = useCallback(
    async (position, blob) => {
      const current = sessionRef.current;
      pendingRef.current = { position, blob };
      setUploading(true);
      setUploadFailed(false);
      try {
        applyState(await submitVoiceAnswer(current.session_id, position, blob));
      } catch {
        try {
          const latest = await getVoiceState(current.session_id);
          if (latest.position !== position || !ACTIVE.includes(latest.status)) applyState(latest);
          else setUploadFailed(true);
        } catch {
          setUploadFailed(true);
        }
      } finally {
        setUploading(false);
      }
    },
    [applyState],
  );

  const position = session.position;
  const recorder = useAnswerRecorder(stream, (blob) => {
    if (position !== null) void send(position, blob);
  });

  // Speak the question when audio is available. The text is always shown, so a failure costs nothing.
  const sessionId = session.session_id;
  useEffect(() => {
    if (position === null) return undefined;
    let cancelled = false;
    let url = null;
    (async () => {
      const blob = await fetchQuestionAudio(sessionId, position);
      if (cancelled || !blob) return;
      url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch(() => undefined);
    })();
    return () => {
      cancelled = true;
      audioRef.current?.pause();
      audioRef.current = null;
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId, position]);

  if (session.status === 'completed') {
    return (
      <div data-testid="session-complete" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
        <p role="status" className="font-semibold text-emerald-900">
          {completedMessage}
        </p>
      </div>
    );
  }
  if (!ACTIVE.includes(session.status) || position === null) {
    return (
      <p role="status" className="rounded-2xl border border-amber-200 bg-amber-50 p-5 font-semibold text-amber-900">
        {session.status === 'expired' ? t('bridges.voice.expired') : t('bridges.voice.ended')}
      </p>
    );
  }

  const notice =
    session.status === 'paused' ? t('bridges.voice.paused')
      : session.status === 'closing' ? t('bridges.voice.closing')
        : session.notice === 'repeat' ? t('bridges.voice.repeat')
          : session.notice === 'retry' ? t('bridges.voice.retry') : null;

  return (
    <div className="space-y-4">
      <div
        data-testid="recording-indicator"
        data-recording={recorder.isRecording ? 'true' : 'false'}
        role="status"
        className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 px-4 py-2 text-sm font-bold text-red-700"
      >
        <span className={`h-3 w-3 rounded-full bg-red-600 ${recorder.isRecording ? 'animate-pulse' : ''}`} />
        {recorder.isRecording ? t('bridges.voice.recordingOn') : t('bridges.voice.recordingSession')}
      </div>

      <div className="flex items-center justify-between text-sm text-slate-600">
        <span data-testid="question-progress">{t('bridges.voice.questionOf', { current: position, total: session.total })}</span>
        <span>
          {t('bridges.voice.timeLeft')}: <span data-testid="time-left">{formatClock(remaining)}</span>
        </span>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        {session.is_followup && <p className="mb-1 text-xs font-bold uppercase text-blue-600">{t('bridges.voice.followup')}</p>}
        <p data-testid="question-text" className="text-lg font-semibold">
          {session.question_text}
        </p>
        {session.why && (
          <p className="mt-3 text-sm text-slate-600">
            <span className="font-bold">{t('bridges.voice.why')}:</span> {session.why}
          </p>
        )}
      </section>

      {notice && (
        <p role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {notice}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        {!recorder.isRecording ? (
          <button
            type="button"
            data-testid="record-answer"
            onClick={() => {
              audioRef.current?.pause();
              recorder.start();
            }}
            disabled={!stream || uploading || uploadFailed}
            className="rounded-xl bg-blue-600 px-5 py-3 font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t('bridges.voice.record')}
          </button>
        ) : (
          <button
            type="button"
            data-testid="stop-answer"
            onClick={recorder.stop}
            className="rounded-xl bg-red-600 px-5 py-3 font-bold text-white hover:bg-red-700"
          >
            {t('bridges.voice.stop')} ({formatClock(recorder.elapsed)} / {formatClock(MAX_ANSWER_SECONDS)})
          </button>
        )}
        {uploadFailed && (
          <button
            type="button"
            onClick={() => pendingRef.current && void send(pendingRef.current.position, pendingRef.current.blob)}
            className="rounded-xl border border-slate-200 bg-white px-5 py-3 font-bold hover:bg-slate-50"
          >
            {t('bridges.voice.retrySend')}
          </button>
        )}
      </div>
      {uploading && <p role="status">{t('bridges.voice.uploading')}</p>}
      {uploadFailed && (
        <p role="alert" className="text-sm text-red-600">
          {t('bridges.voice.uploadFailed')}
        </p>
      )}
      {recorder.error && (
        <p role="alert" className="text-sm text-red-600">
          {t('bridges.voice.recordError')}
        </p>
      )}
    </div>
  );
}

export default VoiceRoom;
