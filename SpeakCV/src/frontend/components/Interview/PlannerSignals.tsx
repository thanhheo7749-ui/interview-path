/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { BrainCircuit, ShieldCheck, Activity, Sparkles } from "lucide-react";
import type { InterviewAnalysis } from "@/hooks/useChat";

interface PlannerSignalsProps {
  currentFocus?: string;
  whySelected?: string;
  nextSkill?: string;
  liveCues?: string[];
  analysis?: InterviewAnalysis | null;
}

const WHY_REASON_LABELS: Record<string, string> = {
  gap_in_jd: "Probing JD Skill Gap (Missing in CV)",
  previous_answer_shallow: "Deep-Dive Follow-Up (Needs STAR Detail)",
  strong_performance_raise_difficulty: "Stretch Challenge (Strong Prior Answer)",
  clarify_low_quality_transcript: "Clarifying Ambiguous Response",
};

const INTENT_LABELS: Record<string, string> = {
  answering: "Direct Engagement",
  skipping: "Topic Evasion Detected",
  asking_reverse_question: "Reverse Question Deflection",
};

const formatLabel = (value?: string) => {
  if (!value) return "";
  const normalized = value.trim().toLowerCase();
  if (WHY_REASON_LABELS[normalized]) {
    return WHY_REASON_LABELS[normalized];
  }

  return value
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const toFiveScale = (val?: number) => {
  if (typeof val !== "number" || Number.isNaN(val)) return null;
  return Math.max(1, Math.min(5, Math.round(val * 5)));
};

const cuePalette = [
  "bg-blue-500/10 text-blue-300 border-blue-500/20",
  "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  "bg-violet-500/10 text-violet-300 border-violet-500/20",
  "bg-amber-500/10 text-amber-300 border-amber-500/20",
];

export function PlannerSignals({
  currentFocus,
  whySelected,
  nextSkill,
  liveCues = [],
  analysis,
}: PlannerSignalsProps) {
  const focus = formatLabel(currentFocus);
  const why = formatLabel(whySelected);
  const next = formatLabel(nextSkill);
  const cues = liveCues.filter(Boolean);

  const confidenceLevel = analysis?.confidence_level as string | undefined;
  const intentRaw = analysis?.intent as string | undefined;
  const fillerCount =
    typeof analysis?.filler_count === "number" ? analysis.filler_count : null;

  const nunchiSummary = confidenceLevel
    ? `${confidenceLevel} • ${INTENT_LABELS[intentRaw || "answering"] || formatLabel(intentRaw)}${
        fillerCount !== null ? ` (${fillerCount} fillers)` : ""
      }`
    : "";

  const turnEval = analysis?.turn_evaluation;
  const correctness5 = toFiveScale(turnEval?.correctness);
  const depth5 = toFiveScale(turnEval?.depth);
  const communication5 = toFiveScale(turnEval?.communication);
  const hasTurnScores =
    correctness5 !== null || depth5 !== null || communication5 !== null;

  if (!focus && !why && !next && !nunchiSummary && cues.length === 0) {
    return null;
  }

  return (
    <section className="w-full max-w-6xl z-10 mb-5 animate-in fade-in slide-in-from-bottom-2">
      <div className="bg-theme-primary/75 border border-theme-border/50 rounded-3xl px-5 py-4 backdrop-blur-md shadow-xl space-y-3">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-theme-border/30 pb-2.5">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-400">
            <BrainCircuit size={15} />
            <span>Explainable AI Question Planner &amp; HR Signals</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {hasTurnScores && (
              <div className="flex items-center gap-2 text-[11px] font-semibold bg-theme-secondary/80 border border-theme-border/40 px-3 py-1 rounded-full text-slate-300">
                <Activity size={12} className="text-emerald-400" />
                <span>Turn Rubric:</span>
                {correctness5 !== null && (
                  <span className="text-emerald-300">
                    Correctness {correctness5}/5
                  </span>
                )}
                {depth5 !== null && (
                  <span className="text-blue-300">• Depth {depth5}/5</span>
                )}
                {communication5 !== null && (
                  <span className="text-violet-300">
                    • STAR Comm {communication5}/5
                  </span>
                )}
              </div>
            )}
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
              <ShieldCheck size={12} /> PII Masked
            </span>
          </div>
        </div>

        {/* 4-Column Signal Grid */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SignalItem label="Current Focus" value={focus} />
          <SignalItem
            label="Why AI Selected This Question"
            value={why}
            highlight
          />
          <SignalItem label="Next Skill Target" value={next} />
          <SignalItem
            label="Nunchi Signal (눈치 Attitude)"
            value={nunchiSummary || "Calibrating candidate confidence..."}
          />
        </div>

        {/* Live Cues Row */}
        {cues.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-[11px] font-bold uppercase tracking-[0.15em] text-theme-text-secondary flex items-center gap-1 mr-1">
              <Sparkles size={12} className="text-amber-400" /> Live Cues:
            </span>
            {cues.map((cue, index) => (
              <span
                key={`${cue}-${index}`}
                className={`inline-flex items-center rounded-full border px-3 py-0.5 text-xs font-semibold ${cuePalette[index % cuePalette.length]}`}
              >
                {cue}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function SignalItem({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`min-w-0 rounded-2xl border px-4 py-2.5 ${
        highlight
          ? "border-cyan-500/30 bg-cyan-500/5"
          : "border-theme-border/30 bg-theme-primary/40"
      }`}
    >
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-theme-muted mb-1">
        {label}
      </div>
      <div className="text-xs sm:text-sm font-medium text-theme-text leading-snug break-words">
        {value || "Waiting for the next signal..."}
      </div>
    </div>
  );
}
