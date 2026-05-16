/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { User, AlertCircle, CameraOff } from "lucide-react";

interface WebcamViewProps {
  onStreamReady?: (stream: MediaStream) => void;
  className?: string;
}

export function WebcamView({ onStreamReady, className = "" }: WebcamViewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);

  useEffect(() => {
    let activeStream: MediaStream | null = null;

    const startWebcam = async () => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          throw new Error("Browser does not support Camera.");
        }

        activeStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false, // We use the existing audio logic in SpeakCV
        });

        setStream(activeStream);

        if (onStreamReady) {
          onStreamReady(activeStream);
        }
      } catch (err: any) {
        console.error("Error accessing camera:", err);
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setError("Please grant Camera access to use this feature.");
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          setError("No Camera found on your device.");
        } else {
          setError("Cannot connect to Camera. Please try again.");
        }
      }
    };

    startWebcam();

    return () => {
      if (activeStream) {
        activeStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [onStreamReady]);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <div className={`relative bg-slate-900 overflow-hidden flex items-center justify-center ${className}`}>
      {error ? (
        <div className="flex flex-col items-center justify-center p-6 text-center h-full w-full">
          <CameraOff className="w-12 h-12 text-slate-500 mb-3" />
          <p className="text-slate-400 text-sm">{error}</p>
        </div>
      ) : stream ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover -scale-x-100" // Mirror effect
        />
      ) : (
        <div className="flex flex-col items-center justify-center text-slate-500 animate-pulse">
          <User className="w-16 h-16 mb-2 opacity-50" />
          <span className="text-xs font-semibold">Loading Camera...</span>
        </div>
      )}
      
      {/* Name Tag Overlay */}
      <div className="absolute bottom-4 left-4 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg text-white text-xs font-medium border border-white/10 shadow-lg flex items-center gap-2 z-10">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
        You
      </div>
    </div>
  );
}
