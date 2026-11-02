import { useCallback, useEffect, useRef, useState } from 'react';

export const MAX_ANSWER_SECONDS = 180;
const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];

export function supportsRecording() {
  return typeof window.MediaRecorder !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia);
}

const pickMime = () => MIME_CANDIDATES.find((type) => window.MediaRecorder.isTypeSupported?.(type));

// Records one answer at a time from an already open stream. The caller owns the stream and releases its tracks.
export function useAnswerRecorder(stream, onBlob) {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [limitSeconds, setLimitSeconds] = useState(MAX_ANSWER_SECONDS);
  const [error, setError] = useState(false);
  const recorderRef = useRef(null);
  const timerRef = useRef(null);
  const onBlobRef = useRef(onBlob);
  const discardRef = useRef(false);

  useEffect(() => {
    onBlobRef.current = onBlob;
  });

  const clearTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
  }, []);

  // Stops and sends itself after `maxSeconds`: the 3 minute limit, or the time left in the session if that is less.
  const start = useCallback((maxSeconds = MAX_ANSWER_SECONDS) => {
    if (!stream || recorderRef.current) return;
    const limit = Math.max(1, Math.min(MAX_ANSWER_SECONDS, Math.floor(maxSeconds)));
    setError(false);
    try {
      const mimeType = pickMime();
      const recorder = new window.MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks = [];
      discardRef.current = false;
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recorder.onerror = () => setError(true);
      recorder.onstop = () => {
        clearTimer();
        recorderRef.current = null;
        setIsRecording(false);
        if (discardRef.current) return;
        const blob = new Blob(chunks, { type: recorder.mimeType || mimeType || 'audio/webm' });
        if (blob.size) onBlobRef.current(blob);
        else setError(true);
      };
      recorderRef.current = recorder;
      recorder.start();
      setElapsed(0);
      setLimitSeconds(limit);
      setIsRecording(true);
      const startedAt = Date.now();
      timerRef.current = setInterval(() => {
        const seconds = Math.floor((Date.now() - startedAt) / 1000);
        setElapsed(seconds);
        if (seconds >= limit) stop();
      }, 250);
    } catch {
      recorderRef.current = null;
      setError(true);
    }
  }, [stream, clearTimer, stop]);

  // On unmount: drop any recording in progress and the timer.
  useEffect(
    () => () => {
      discardRef.current = true;
      clearTimer();
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== 'inactive') recorder.stop();
    },
    [clearTimer],
  );

  return { isRecording, elapsed, limitSeconds, error, start, stop };
}
