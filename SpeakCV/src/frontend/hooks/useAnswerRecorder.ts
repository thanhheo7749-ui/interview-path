"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const MAX_ANSWER_SECONDS = 180;
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

export function supportsRecording(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

function pickMime(): string | undefined {
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported?.(type));
}

/** Records one answer at a time from an already-open stream. The stream is owned by the caller. */
export function useAnswerRecorder(stream: MediaStream | null, onBlob: (blob: Blob) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
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
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }, []);

  const start = useCallback(() => {
    if (!stream || recorderRef.current) return;
    setError(false);
    try {
      const mimeType = pickMime();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
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
        const blob = new Blob(chunks, { type: recorder.mimeType || mimeType || "audio/webm" });
        if (blob.size) onBlobRef.current(blob);
        else setError(true);
      };
      recorderRef.current = recorder;
      recorder.start();
      setElapsed(0);
      setIsRecording(true);
      const startedAt = Date.now();
      timerRef.current = setInterval(() => {
        const seconds = Math.floor((Date.now() - startedAt) / 1000);
        setElapsed(seconds);
        if (seconds >= MAX_ANSWER_SECONDS) stop();
      }, 250);
    } catch {
      recorderRef.current = null;
      setError(true);
    }
  }, [stream, clearTimer, stop]);

  // On unmount: drop any recording in progress and the timer. Tracks are released by the stream's owner.
  useEffect(() => {
    return () => {
      discardRef.current = true;
      clearTimer();
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
    };
  }, [clearTimer]);

  return { isRecording, elapsed, error, start, stop };
}
