/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useEffect, useRef, useState } from "react";

export function useAudioAnalyser(audioElement: HTMLAudioElement | null | undefined, isPlaying: boolean) {
  const [amplitude, setAmplitude] = useState(0);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const requestRef = useRef<number | null>(null);

  useEffect(() => {
    // If we have an audio element but no context yet, initialize it
    if (audioElement && !audioContextRef.current) {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return;

      const audioCtx = new AudioContextClass();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;

      try {
        const source = audioCtx.createMediaElementSource(audioElement);
        source.connect(analyser);
        analyser.connect(audioCtx.destination);
        
        audioContextRef.current = audioCtx;
        analyserRef.current = analyser;
        sourceRef.current = source;
      } catch (e) {
        console.warn("Could not create media element source:", e);
      }
    }

    return () => {
      // Cleanup on unmount
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
      }
      
      // Note: We don't close the audio context completely here because the audio element
      // might be reused across modal opens/closes.
    };
  }, [audioElement]);

  useEffect(() => {
    if (!isPlaying || !analyserRef.current) {
      setAmplitude(0);
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
      return;
    }

    // Need to resume context in case browser suspended it
    if (audioContextRef.current?.state === "suspended") {
      audioContextRef.current.resume();
    }

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

    const updateAmplitude = () => {
      if (!analyserRef.current) return;
      
      analyserRef.current.getByteFrequencyData(dataArray);
      
      // Calculate average amplitude
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;
      
      // Normalize to 0.0 - 1.0 (average usually stays below 100)
      const normalized = Math.min(1.0, average / 100);
      setAmplitude(normalized);
      
      requestRef.current = requestAnimationFrame(updateAmplitude);
    };

    updateAmplitude();

    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [isPlaying]);

  return amplitude;
}
