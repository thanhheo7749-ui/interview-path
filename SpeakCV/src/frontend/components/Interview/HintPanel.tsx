/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useRef, useState } from "react";
import { Lightbulb, X } from "lucide-react";

interface HintPanelProps {
  hint: { show: boolean; content: string };
  onClose: () => void;
}

export function HintPanel({ hint, onClose }: HintPanelProps) {
  const touchStartY = useRef(0);
  const [swipeOffset, setSwipeOffset] = useState(0);

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY;
    setSwipeOffset(0);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    const delta = e.touches[0].clientY - touchStartY.current;
    if (delta > 0) setSwipeOffset(delta);
  };

  const handleTouchEnd = () => {
    if (swipeOffset > 80) onClose();
    setSwipeOffset(0);
  };

  if (!hint.show) return null;

  return (
    <>
      {/* Desktop popover - positioned relative to the nearest `relative` ancestor */}
      <div className="hidden md:flex absolute left-full top-0 ml-8 z-50 w-[420px] max-h-[220px] flex-col bg-theme-primary/95 p-5 rounded-2xl border border-yellow-500/50 shadow-[0_0_40px_-10px_rgba(234,179,8,0.3)] backdrop-blur-md animate-in fade-in slide-in-from-left-5 origin-top-left">
        <button
          onClick={onClose}
          aria-label="Close hint"
          className="absolute top-3 right-3 text-theme-muted hover:text-theme-text transition-colors bg-theme-surface/50 rounded-full p-1.5 hover:bg-slate-700/50 z-10"
        >
          <X size={16} />
        </button>

        <div className="flex items-center gap-2 mb-3 text-yellow-400 font-semibold uppercase text-xs tracking-wider shrink-0">
          <Lightbulb size={14} /> AI Hint
        </div>

        <div className="text-sm text-theme-text-secondary leading-relaxed whitespace-pre-wrap break-words font-medium pl-1 overflow-y-auto pr-3 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:bg-slate-700 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent hover:[&::-webkit-scrollbar-thumb]:bg-slate-500 transition-colors">
          {hint.content}
        </div>
      </div>

      {/* Mobile sheet, swipe down to dismiss */}
      <div
        className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:hidden"
        role="dialog"
        aria-modal="true"
        aria-label="AI Hint"
      >
        <div className="absolute inset-0 bg-slate-900/45 backdrop-blur-sm" onClick={onClose} />
        <div
          className="relative w-full max-w-sm max-h-[80vh] flex flex-col bg-theme-primary border border-yellow-500/50 shadow-[0_0_40px_-10px_rgba(234,179,8,0.3)] rounded-2xl p-5 animate-in zoom-in-95"
          style={{
            transform: `translateY(${swipeOffset}px)`,
            opacity: swipeOffset > 60 ? 0.5 : 1,
            transition: swipeOffset === 0 ? "transform 0.2s, opacity 0.2s" : "none",
          }}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          <button
            onClick={onClose}
            aria-label="Close hint"
            className="absolute top-3 right-3 text-theme-muted hover:text-theme-text transition-colors bg-theme-surface/50 rounded-full p-1.5 hover:bg-slate-700/50 z-10"
          >
            <X size={16} />
          </button>

          <div className="flex items-center gap-2 mb-3 text-yellow-400 font-semibold uppercase text-xs tracking-wider shrink-0">
            <Lightbulb size={14} /> AI Hint
          </div>

          <div className="text-sm text-theme-text-secondary leading-relaxed whitespace-pre-wrap break-words font-medium pl-1 overflow-y-auto pr-3 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:bg-slate-700 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent hover:[&::-webkit-scrollbar-thumb]:bg-slate-500 transition-colors">
            {hint.content}
          </div>
        </div>
      </div>
    </>
  );
}
