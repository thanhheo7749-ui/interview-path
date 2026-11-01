"use client";

import { useEffect, useRef, useState } from "react";
import type { ScreeningText } from "@/lib/i18n";

interface Props {
  text: ScreeningText;
  /** Called with the open stream once the microphone is allowed. The parent owns and releases it. */
  onStream: (stream: MediaStream) => void;
}

/** Opens the microphone and shows a live level. Owns the audio analysis only. */
export function MicCheck({ text, onStream }: Props) {
  const [level, setLevel] = useState(0);
  const [heard, setHeard] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const begin = async () => {
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = (e as DOMException)?.name;
      setError(name === "NotFoundError" || name === "OverconstrainedError" ? text.micMissing : text.micDenied);
      return;
    }
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    let frame = 0;
    let loud = false;
    const tick = () => {
      analyser.getByteFrequencyData(data);
      const average = data.reduce((sum, v) => sum + v, 0) / data.length;
      const value = Math.min(1, average / 60);
      setLevel(value);
      if (!loud && value > 0.15) {
        loud = true;
        setHeard(true);
      }
      frame = requestAnimationFrame(tick);
    };
    tick();
    cleanupRef.current = () => {
      cancelAnimationFrame(frame);
      ctx.close().catch(() => undefined);
    };
    setActive(true);
    onStream(stream);
  };

  return (
    <section className="rounded-2xl border border-theme-border bg-theme-primary p-5">
      <h2 className="font-bold text-theme-text">{text.micTitle}</h2>
      <p className="mt-1 text-sm text-theme-text-secondary">{text.micHelp}</p>
      {!active && (
        <button type="button" onClick={begin} className="mt-3 rounded-xl bg-blue-600 px-4 py-2 font-bold text-white hover:bg-blue-700">
          {text.micStart}
        </button>
      )}
      <div
        data-testid="mic-level"
        data-level={level.toFixed(2)}
        data-heard={heard ? "true" : "false"}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={Number(level.toFixed(2))}
        aria-label={text.micTitle}
        className="mt-3 h-3 w-full overflow-hidden rounded-full bg-theme-secondary"
      >
        <div className="h-full bg-green-500 transition-[width] duration-75" style={{ width: `${Math.round(level * 100)}%` }} />
      </div>
      {active && <p className="mt-2 text-sm text-theme-text-secondary">{heard ? text.micHeard : text.micQuiet}</p>}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </section>
  );
}
