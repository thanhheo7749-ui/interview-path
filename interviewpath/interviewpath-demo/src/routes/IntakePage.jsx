import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { ErrorAlert, cardClass, primaryButton } from '../components/KbFeedback.jsx';
import VoiceRoom, { MicCheck, stopStream } from '../components/voice/VoiceRoom.jsx';
import { supportsRecording } from '../hooks/useAnswerRecorder.js';
import { getHiringRequest, startIntake } from '../lib/bridges.js';

const SESSION_LANGUAGES = ['ko', 'vi', 'en'];
const OPEN = ['open', 'intake_in_progress', 'intake_empty'];

// The manager's voice interview about a hiring request. Everything the manager must know is shown before the
// microphone is used: that it is recorded, where the transcript goes, and not to name people.
function IntakePage() {
  const { t, i18n } = useTranslation();
  const { requestId } = useParams();
  const { membership } = useCompany();
  const companyId = membership?.company_id ?? null;
  const [request, setRequest] = useState(null);
  const [error, setError] = useState('');
  const [stream, setStream] = useState(null);
  const streamRef = useRef(null);
  const [understood, setUnderstood] = useState(false);
  const [starting, setStarting] = useState(false);
  const [session, setSession] = useState(null);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    if (companyId == null) return undefined;
    let cancelled = false;
    getHiringRequest(companyId, requestId)
      .then((data) => {
        if (!cancelled) setRequest(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.status === 404 ? t('bridges.intake.notFound') : err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, requestId, t]);

  // Release the microphone if the page is left before or after the session.
  useEffect(
    () => () => {
      stopStream(streamRef.current);
      streamRef.current = null;
    },
    [],
  );

  const adoptStream = useCallback((next) => {
    if (streamRef.current && streamRef.current !== next) stopStream(streamRef.current);
    streamRef.current = next;
    setStream(next);
  }, []);

  const start = async () => {
    setError('');
    setStarting(true);
    try {
      const language = SESSION_LANGUAGES.includes(i18n.language) ? i18n.language : 'en';
      setSession(await startIntake(companyId, requestId, language));
    } catch (err) {
      setError(err.status === 409 ? t('bridges.intake.alreadyDone') : err.message);
    } finally {
      setStarting(false);
    }
  };

  const shell = (children) => (
    <div className="max-w-2xl space-y-4 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('bridges.intake.title')}</h1>
      {request && <p className="text-sm font-semibold text-slate-600">{request.title}</p>}
      {children}
    </div>
  );

  const back = (
    <Link to="/hiring-requests" className="inline-block text-sm font-bold text-blue-700 underline">
      {t('bridges.intake.back')}
    </Link>
  );

  if (!request) {
    return shell(error ? <><ErrorAlert message={error} />{back}</> : <p role="status">{t('common.loading')}</p>);
  }
  if (!supportsRecording()) {
    return shell(<><ErrorAlert message={t('bridges.voice.unsupported')} />{back}</>);
  }

  if (session) {
    return shell(
      <>
        <VoiceRoom
          initialState={session}
          stream={stream}
          completedMessage={t('bridges.intake.completed')}
          onFinished={() => {
            setFinished(true);
            setStream(null);
            streamRef.current = null;
          }}
        />
        {finished && back}
      </>,
    );
  }

  if (!OPEN.includes(request.status)) {
    return shell(<><p role="status" className={cardClass}>{t('bridges.intake.alreadyDone')}</p>{back}</>);
  }

  return shell(
    <>
      <section data-testid="recording-notice" className="space-y-2 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-900">
        <h2 className="font-bold">{t('bridges.intake.noticeTitle')}</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>{t('bridges.intake.noticeRecorded')}</li>
          <li>{t('bridges.intake.noticeTranscript')}</li>
          <li>{t('bridges.intake.noticeNoNames')}</li>
        </ul>
      </section>
      <MicCheck onStream={adoptStream} />
      <section className={cardClass}>
        <label className="flex items-start gap-2 text-sm">
          <input
            data-testid="intake-understood"
            type="checkbox"
            checked={understood}
            onChange={(e) => setUnderstood(e.target.checked)}
            className="mt-1"
          />
          <span>{t('bridges.intake.understood')}</span>
        </label>
        <ErrorAlert message={error} />
        <button
          type="button"
          data-testid="start-intake"
          onClick={start}
          disabled={!understood || !stream || starting}
          className={`${primaryButton} mt-4`}
        >
          {starting ? t('bridges.intake.starting') : t('bridges.intake.start')}
        </button>
      </section>
      {back}
    </>,
  );
}

export default IntakePage;
