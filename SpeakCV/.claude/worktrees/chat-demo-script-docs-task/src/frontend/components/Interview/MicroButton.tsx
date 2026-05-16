/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { AudioWave } from "./AudioWave";
import { StopCircle } from "lucide-react";

interface MicroButtonProps {
  status: string;
  onClick: () => void;
  langLabel: string;
  isCompact?: boolean;
}

export const MicroButton = ({
  status,
  onClick,
  langLabel,
  isCompact = false,
}: MicroButtonProps) => {
  const isActive = status === "Processing" || status === "AI Speaking";
  const isListening = status === "Listening";

  return (
    <div className="relative group z-10">
      {/* Glow background effect */}
      <div
        className={`absolute -inset-8 rounded-full blur-3xl transition-opacity duration-500 ${isListening ? "opacity-100 bg-red-500/20" : isActive ? "opacity-100 bg-yellow-500/20" : "opacity-20 bg-blue-500/20"}`}
      ></div>

      <button
        id="tour-step-mic"
        onClick={onClick}
        className={`${isCompact ? "w-32 h-32" : "w-52 h-52"} rounded-full bg-theme-surface/80 backdrop-blur-sm border-2 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 shadow-2xl relative z-10 hover:scale-105 active:scale-95 
          ${isListening ? "border-red-500 shadow-red-900/40" : isActive ? "border-yellow-500 shadow-yellow-900/40" : "border-theme-border hover:border-blue-500 shadow-blue-900/20"}
        `}
      >
        <span
          className={`${isCompact ? "text-[8px] mb-2" : "text-[10px] mb-6"} font-bold uppercase tracking-widest transition-colors ${isListening ? "text-red-400 animate-pulse" : "text-blue-400"}`}
        >
          {isActive ? "CLICK TO STOP" : status}
        </span>

        {isActive ? (
          <StopCircle className="animate-pulse text-yellow-500" size={isCompact ? 36 : 56} />
        ) : isListening ? (
          <div className={isCompact ? "scale-50 origin-center" : ""}>
            <AudioWave state="listening" />
          </div>
        ) : (
          <div className={isCompact ? "scale-50 origin-center" : ""}>
            <AudioWave state="idle" />
          </div>
        )}
      </button>

      {/* Language label */}
      <div className={`absolute ${isCompact ? "-bottom-6" : "-bottom-10"} left-1/2 -translate-x-1/2 whitespace-nowrap`}>
        <span
          className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded border border-blue-200 text-blue-700 bg-blue-50"
        >
          Mic: {langLabel}
        </span>
      </div>
    </div>
  );
};
