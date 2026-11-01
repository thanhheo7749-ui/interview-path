/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */
import { useRef } from "react";
import { RefreshCcw, Eraser, Send, Sparkles } from "lucide-react";

interface ChatBoxProps {
  userText: string;
  tempText: string;
  aiText: string;
  status: string;
  onUserTextChange: (text: string) => void;
  onSend: () => void;
  onClear: () => void;
  onRefresh: () => void;
}

const DEMO_SAMPLE_ANSWERS = [
  {
    label: "⚡ Turn 1: Shallow Answer",
    text: "I used Redis caching in my university backend project to make the API faster, and worked with my teammates to finish before the deadline.",
  },
  {
    label: "🌟 Turn 2: Strong STAR + Ownership",
    text: "In our 4-person sprint, our FastAPI endpoint hit 1,200ms latency under 5,000 RPS. I took ownership of designing a Redis write-through cache with a 60s TTL and fallback circuit breaker, reducing p95 latency by 62% and delivering on schedule.",
  },
];

export const ChatBox = ({
  userText,
  tempText,
  aiText,
  status,
  onUserTextChange,
  onSend,
  onClear,
  onRefresh,
}: ChatBoxProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleFocus = () => {
    // On mobile, scroll textarea into view when keyboard opens
    setTimeout(() => {
      textareaRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 300);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-6xl h-72 z-10">
      {/* User's panel */}
      <div className="bg-theme-primary/60 border border-theme-border/30 rounded-3xl p-4 backdrop-blur-md shadow-xl flex flex-col hover:border-blue-500/20 transition-colors relative">
        <div className="flex flex-wrap justify-between items-center gap-2 mb-2 px-2">
          <span className="text-xs font-bold text-blue-500 uppercase tracking-widest flex items-center gap-2">
            Candidate (You)
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {DEMO_SAMPLE_ANSWERS.map((sample) => (
              <button
                key={sample.label}
                type="button"
                onClick={() => onUserTextChange(sample.text)}
                className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-500/10 hover:bg-blue-500/25 border border-blue-500/30 text-blue-300 transition-colors flex items-center gap-1"
                title="Click to populate sample answer for video demo"
              >
                <Sparkles size={10} /> {sample.label}
              </button>
            ))}
            <button
              onClick={onClear}
              className="p-1.5 hover:bg-theme-surface rounded-lg text-theme-muted hover:text-red-400"
              title="Clear"
            >
              <Eraser size={16} />
            </button>
            <button
              onClick={onRefresh}
              className="p-1.5 hover:bg-theme-surface rounded-lg text-theme-muted hover:text-theme-text"
              title="Refresh Mic"
            >
              <RefreshCcw size={16} />
            </button>
          </div>
        </div>
        <div className="flex-1 relative bg-theme-primary/30 rounded-xl border border-theme-border/30 overflow-hidden focus-within:border-blue-500/50 transition-colors">
          <textarea
            ref={textareaRef}
            className="w-full h-full bg-transparent p-4 outline-none resize-none text-theme-text-secondary text-lg leading-relaxed custom-scrollbar placeholder:text-theme-muted"
            placeholder="Speak, type, or click a 1-Click Demo Answer above..."
            value={userText}
            onChange={(e) => onUserTextChange(e.target.value)}
            onFocus={handleFocus}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
          />
          {tempText && (
            <div className="pointer-events-none absolute left-4 right-14 bottom-4 text-base text-theme-muted italic truncate">
              {tempText}
            </div>
          )}
          <button
            onClick={onSend}
            disabled={(!userText && !tempText) || status === "Processing"}
            className="absolute bottom-3 right-3 bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-lg shadow-md disabled:opacity-50 transition-all active:scale-95"
          >
            <Send size={20} />
          </button>
        </div>
      </div>

      {/* AI's panel */}
      <div className="bg-theme-primary border border-theme-border rounded-2xl p-6 shadow-md flex flex-col">
        <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>{" "}
          AI Response
        </span>
        <p className="text-xl text-theme-text leading-relaxed overflow-y-auto custom-scrollbar flex-1 whitespace-pre-wrap">
          {aiText}
        </p>
      </div>
    </div>
  );
};
