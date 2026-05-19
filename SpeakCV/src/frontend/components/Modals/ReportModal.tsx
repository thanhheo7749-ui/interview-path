/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import {
  X,
  Trophy,
  Target,
  MessageCircle,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Mic,
  BarChart3,
  Quote,
  Brain,
  TrendingUp,
  Volume2,
  Gauge,
  Zap,
} from "lucide-react";
import { useState } from "react";

// === DIMENSION SCORE BAR ===
function DimensionBar({ dimension, score, weight, reasoning, cited_quotes }: any) {
  const [showDetail, setShowDetail] = useState(false);
  const percentage = (score / 10) * 100;
  const color =
    score >= 8
      ? "from-emerald-500 to-emerald-400"
      : score >= 5
        ? "from-yellow-500 to-amber-400"
        : "from-red-500 to-rose-400";
  const textColor =
    score >= 8 ? "text-emerald-400" : score >= 5 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="mb-4">
      <div
        className="flex items-center justify-between mb-2 cursor-pointer group"
        onClick={() => setShowDetail(!showDetail)}
      >
        <div className="flex items-center gap-2 flex-1">
          <span className="text-sm font-semibold text-slate-200">{dimension}</span>
          <span className="text-xs text-slate-500">({(weight * 100).toFixed(0)}%)</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-lg font-black ${textColor}`}>{score?.toFixed(1)}</span>
          <ChevronDown
            size={14}
            className={`text-slate-500 transition-transform ${showDetail ? "rotate-180" : ""}`}
          />
        </div>
      </div>
      <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${color} rounded-full transition-all duration-700`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showDetail && (
        <div className="mt-3 p-4 bg-slate-800/50 rounded-xl border border-slate-700/50 space-y-3 animate-in slide-in-from-top-2 duration-200">
          {reasoning && (
            <p className="text-sm text-slate-300 leading-relaxed">{reasoning}</p>
          )}
          {cited_quotes && cited_quotes.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1.5">
                <Quote size={12} /> Candidate Quotes
              </p>
              {cited_quotes.map((q: string, i: number) => (
                <div
                  key={i}
                  className="text-sm italic text-slate-400 bg-slate-900/50 p-3 rounded-lg border-l-3 border-blue-500/50 pl-4"
                >
                  &ldquo;{q}&rdquo;
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// === VOICE METRICS SECTION ===
function VoiceMetricsSection({ voiceMetrics }: { voiceMetrics: any }) {
  if (!voiceMetrics) return null;

  const { avg_wpm, total_fillers, avg_confidence, top_fillers, feedback_tips } =
    voiceMetrics;

  const confidenceColor =
    avg_confidence >= 80
      ? "text-emerald-400"
      : avg_confidence >= 60
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <div className="mb-8">
      <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-3">
        <Volume2 className="text-cyan-400" size={22} /> Voice Analysis
      </h3>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-slate-800/60 rounded-2xl p-5 border border-slate-700/50 text-center">
          <Gauge size={20} className="text-blue-400 mx-auto mb-2" />
          <p className="text-3xl font-black text-white">{avg_wpm?.toFixed(0) || "—"}</p>
          <p className="text-xs text-slate-500 mt-1">WPM</p>
          <p className="text-[10px] text-slate-600">Ideal: 130-160</p>
        </div>
        <div className="bg-slate-800/60 rounded-2xl p-5 border border-slate-700/50 text-center">
          <Zap size={20} className="text-amber-400 mx-auto mb-2" />
          <p className="text-3xl font-black text-white">{total_fillers ?? "—"}</p>
          <p className="text-xs text-slate-500 mt-1">Filler Words</p>
          {top_fillers && top_fillers.length > 0 && (
            <p className="text-[10px] text-slate-600 truncate">
              {top_fillers.map((f: any) => `"${f.word}"`).join(", ")}
            </p>
          )}
        </div>
        <div className="bg-slate-800/60 rounded-2xl p-5 border border-slate-700/50 text-center">
          <Brain size={20} className={`${confidenceColor} mx-auto mb-2`} />
          <p className={`text-3xl font-black ${confidenceColor}`}>
            {avg_confidence ?? "—"}
          </p>
          <p className="text-xs text-slate-500 mt-1">Confidence</p>
          <p className="text-[10px] text-slate-600">/100</p>
        </div>
      </div>
      {feedback_tips && feedback_tips.length > 0 && (
        <div className="space-y-2">
          {feedback_tips.map((tip: string, i: number) => (
            <div
              key={i}
              className="flex items-start gap-2 text-sm text-slate-400 bg-slate-800/30 p-3 rounded-xl"
            >
              <TrendingUp size={14} className="text-cyan-400 mt-0.5 shrink-0" />
              <span>{tip}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// === MAIN REPORT MODAL ===
export default function ReportModal({
  show,
  onClose,
  result,
  onRetry,
  hasHistory,
  voiceMetrics,
}: any) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(0);

  if (!show) return null;

  // 1. CASE: NO INTERVIEW HISTORY YET
  if (!hasHistory) {
    return (
      <div className="fixed inset-0 bg-black/95 z-50 flex items-center justify-center p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Interview Report">
        <div className="bg-slate-900 w-full max-w-lg p-10 rounded-3xl border border-slate-700 flex flex-col items-center text-center shadow-2xl animate-in zoom-in-95">
          <div className="w-24 h-24 bg-blue-500/10 rounded-full flex items-center justify-center mb-6">
            <Mic size={40} className="text-blue-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">
            No Interview Started
          </h2>
          <p className="text-slate-400 mb-8 leading-relaxed">
            The system needs to collect conversation history to provide evaluation.
            Please start speaking with the AI interviewer first!
          </p>
          <button
            onClick={onClose}
            className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl font-bold text-white w-full transition-all active:scale-95"
          >
            Back to Interview
          </button>
        </div>
      </div>
    );
  }

  // 2. CASE: HAS INTERVIEW HISTORY (RENDER REPORT)
  const report =
    typeof result === "object" && result !== null
      ? result
      : {
          score: 0,
          overall_feedback: "Analyzing data...",
          details: [],
        };

  // Handle both old format (details as array) and new format (details as object with questions/dimension_scores)
  const nestedReport =
    report.details && typeof report.details === "object" && !Array.isArray(report.details)
      ? report.details
      : null;
  const questionDetails = Array.isArray(report.details)
    ? report.details
    : report.details?.questions || nestedReport?.details || [];
  const dimensionScores =
    report.dimension_scores || report.details?.dimension_scores || nestedReport?.dimension_scores || [];
  const learningPlan =
    report.learning_plan || report.details?.learning_plan || nestedReport?.learning_plan || {};
  const finalScores = report.final_scores || nestedReport?.final_scores || {
    correctness: null,
    depth: null,
    communication: null,
    topic_relevance: null,
  };
  const topSkillsToImprove = Array.isArray(report.top_skills_to_improve)
    ? report.top_skills_to_improve.slice(0, 3)
    : [];
  const strongTopics = Array.isArray(report.strong_topics) ? report.strong_topics : [];
  const weakTopics = Array.isArray(report.weak_topics) ? report.weak_topics : [];

  const getScoreColor = (score: number) => {
    if (score >= 8) return "text-emerald-400 border-emerald-400";
    if (score >= 5) return "text-yellow-400 border-yellow-400";
    return "text-red-400 border-red-400";
  };
  const getScoreBg = (score: number) => {
    if (score >= 8) return "bg-emerald-500/10";
    if (score >= 5) return "bg-yellow-500/10";
    return "bg-red-500/10";
  };

  return (
    <div className="fixed inset-0 bg-black/95 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="bg-slate-900 w-full max-w-5xl h-[90vh] rounded-3xl border border-slate-700 flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-300">
        {/* HEADER */}
        <div className="flex justify-between items-center px-8 py-5 border-b border-slate-800 bg-slate-900/50">
          <h2 className="text-2xl font-black flex gap-3 text-white items-center tracking-wide">
            <Trophy className="text-yellow-500" size={28} />
            INTERVIEW ANALYSIS REPORT
          </h2>
          <button
            onClick={onClose}
            className="p-2 bg-slate-800 hover:bg-slate-700 rounded-full transition-colors text-slate-400 hover:text-white"
          >
            <X size={24} />
          </button>
        </div>

        {/* BODY */}
        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          {/* SCORE + FEEDBACK ROW */}
          <div className="flex flex-col md:flex-row gap-8 mb-10">
            <div
              className={`w-full md:w-1/3 rounded-3xl border-2 flex flex-col items-center justify-center p-8 ${getScoreColor(report.score)} ${getScoreBg(report.score)}`}
            >
              <p className="text-slate-300 font-bold uppercase tracking-widest text-sm mb-2 border-b border-current/20 pb-2">
                Overall Score
              </p>
              <div className="text-7xl font-black my-2 tracking-tighter">
                {Math.round(report.score * 10)}
                <span className="text-3xl text-current/50">%</span>
              </div>
              <p className="text-sm font-medium mt-2 opacity-80 text-center">
                {report.score >= 8
                  ? "Excellent! You're ready."
                  : report.score >= 5
                    ? "Good, but room for improvement."
                    : "More practice needed."}
              </p>
            </div>

            <div className="w-full md:w-2/3 bg-slate-800/50 rounded-3xl border border-slate-700 p-8 relative overflow-hidden">
              <div className="absolute -top-4 -right-4 opacity-5">
                <Target size={150} />
              </div>
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Target className="text-blue-400" size={20} /> AI Evaluation Summary
              </h3>
              <p className="text-slate-300 leading-relaxed text-[15px] whitespace-pre-line relative z-10">
                {report.overall_feedback}
              </p>
            </div>
          </div>

          {/* FINAL SCORES */}
          {Object.values(finalScores).some((score) => score !== null && score !== undefined) && (
            <div className="mb-10">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-3">
                <BarChart3 className="text-violet-400" size={22} /> Final 1-5 Scores
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(finalScores).map(([label, score]) => {
                  const displayScore = typeof score === "number" || typeof score === "string" ? score : "—";

                  return (
                    <div
                      key={label}
                      className="rounded-2xl border border-slate-700 bg-slate-800/40 p-4 text-center"
                    >
                      <p className="text-xs uppercase text-slate-500">{label.replace(/_/g, " ")}</p>
                      <p className="mt-2 text-3xl font-black text-white">{displayScore}</p>
                      <p className="text-xs text-slate-500">/5</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TOP SKILLS TO IMPROVE */}
          {topSkillsToImprove.length > 0 && (
            <div className="mb-10">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-3">
                <Brain className="text-pink-400" size={22} /> Top 3 Skills to Improve
              </h3>
              <div className="grid gap-3">
                {topSkillsToImprove.map((skill: string, index: number) => (
                  <div
                    key={`${skill}-${index}`}
                    className="rounded-2xl border border-pink-500/20 bg-pink-500/5 p-4 text-slate-200"
                  >
                    <span className="mr-2 font-bold text-pink-400">{index + 1}.</span>
                    {skill}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* DIMENSION SCORES */}
          {dimensionScores && dimensionScores.length > 0 && (
            <div className="mb-10">
              <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2 border-b border-slate-800 pb-3">
                <BarChart3 className="text-violet-400" size={22} /> Multi-Dimensional Analysis
              </h3>
              <div className="bg-slate-800/30 rounded-2xl p-6 border border-slate-700/50">
                {dimensionScores.map((dim: any, i: number) => (
                  <DimensionBar
                    key={i}
                    dimension={dim.dimension}
                    score={dim.score}
                    weight={dim.weight}
                    reasoning={dim.reasoning}
                    cited_quotes={dim.cited_quotes}
                  />
                ))}
              </div>
            </div>
          )}

          {/* VOICE METRICS */}
          <VoiceMetricsSection voiceMetrics={voiceMetrics} />

          {/* LEARNING PLAN */}
          {learningPlan && (learningPlan.focus_topics?.length > 0 || learningPlan.learning_tips?.length > 0) && (
            <div className="mb-10">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-3">
                <Brain className="text-pink-400" size={22} /> AI Learning Plan
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {learningPlan.weak_areas?.length > 0 && (
                  <div className="bg-red-500/5 border border-red-500/20 p-5 rounded-2xl">
                    <p className="text-xs font-bold text-red-400 uppercase mb-3">Areas to Improve</p>
                    <div className="flex flex-wrap gap-2">
                      {learningPlan.weak_areas.map((area: string, i: number) => (
                        <span key={i} className="text-xs bg-red-500/10 text-red-300 px-3 py-1 rounded-full border border-red-500/20">
                          {area}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {learningPlan.strong_areas?.length > 0 && (
                  <div className="bg-emerald-500/5 border border-emerald-500/20 p-5 rounded-2xl">
                    <p className="text-xs font-bold text-emerald-400 uppercase mb-3">Strengths</p>
                    <div className="flex flex-wrap gap-2">
                      {learningPlan.strong_areas.map((area: string, i: number) => (
                        <span key={i} className="text-xs bg-emerald-500/10 text-emerald-300 px-3 py-1 rounded-full border border-emerald-500/20">
                          {area}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {learningPlan.learning_tips?.length > 0 && (
                <div className="mt-4 space-y-2">
                  {learningPlan.learning_tips.map((tip: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-slate-300 bg-slate-800/40 p-3 rounded-xl">
                      <TrendingUp size={14} className="text-pink-400 mt-0.5 shrink-0" />
                      <span>{tip}</span>
                    </div>
                  ))}
                </div>
              )}
              {(weakTopics.length > 0 || strongTopics.length > 0) && (
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {weakTopics.length > 0 && (
                    <div className="bg-red-500/5 border border-red-500/20 p-5 rounded-2xl">
                      <p className="text-xs font-bold text-red-400 uppercase mb-3">Weak Topics</p>
                      <div className="flex flex-wrap gap-2">
                        {weakTopics.map((topic: string, i: number) => (
                          <span
                            key={i}
                            className="text-xs bg-red-500/10 text-red-300 px-3 py-1 rounded-full border border-red-500/20"
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {strongTopics.length > 0 && (
                    <div className="bg-emerald-500/5 border border-emerald-500/20 p-5 rounded-2xl">
                      <p className="text-xs font-bold text-emerald-400 uppercase mb-3">Strong Topics</p>
                      <div className="flex flex-wrap gap-2">
                        {strongTopics.map((topic: string, i: number) => (
                          <span
                            key={i}
                            className="text-xs bg-emerald-500/10 text-emerald-300 px-3 py-1 rounded-full border border-emerald-500/20"
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {(weakTopics.length > 0 || strongTopics.length > 0) && !learningPlan && (
            <div className="mb-10 grid grid-cols-1 md:grid-cols-2 gap-4">
              {weakTopics.length > 0 && (
                <div className="bg-red-500/5 border border-red-500/20 p-5 rounded-2xl">
                  <p className="text-xs font-bold text-red-400 uppercase mb-3">Weak Topics</p>
                  <div className="flex flex-wrap gap-2">
                    {weakTopics.map((topic: string, i: number) => (
                      <span
                        key={i}
                        className="text-xs bg-red-500/10 text-red-300 px-3 py-1 rounded-full border border-red-500/20"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {strongTopics.length > 0 && (
                <div className="bg-emerald-500/5 border border-emerald-500/20 p-5 rounded-2xl">
                  <p className="text-xs font-bold text-emerald-400 uppercase mb-3">Strong Topics</p>
                  <div className="flex flex-wrap gap-2">
                    {strongTopics.map((topic: string, i: number) => (
                      <span
                        key={i}
                        className="text-xs bg-emerald-500/10 text-emerald-300 px-3 py-1 rounded-full border border-emerald-500/20"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* QUESTION DETAILS */}
          <div className="mb-6">
            <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2 border-b border-slate-800 pb-4">
              <MessageCircle className="text-purple-400" size={24} /> Detailed Question Analysis
            </h3>
            {questionDetails && questionDetails.length > 0 ? (
              <div className="space-y-4">
                {questionDetails.map((item: any, index: number) => (
                  <div
                    key={index}
                    className="bg-slate-950 border border-slate-700 rounded-2xl overflow-hidden"
                  >
                    <div
                      onClick={() =>
                        setExpandedIndex(expandedIndex === index ? null : index)
                      }
                      className="p-5 flex justify-between items-center cursor-pointer hover:bg-slate-800/80"
                    >
                      <div className="flex gap-4 items-center">
                        <span className="bg-blue-600/20 text-blue-400 font-black text-lg w-10 h-10 flex items-center justify-center rounded-xl shrink-0">
                          {index + 1}
                        </span>
                        <h4 className="font-bold text-white text-[15px] line-clamp-2 pr-4">
                          {item.question}
                        </h4>
                      </div>
                      <div className="text-slate-500">
                        {expandedIndex === index ? (
                          <ChevronUp size={24} />
                        ) : (
                          <ChevronDown size={24} />
                        )}
                      </div>
                    </div>
                    {expandedIndex === index && (
                      <div className="p-6 pt-2 bg-slate-900 border-t border-slate-800 space-y-6">
                        <div>
                          <p className="text-xs font-bold text-slate-500 uppercase mb-2">
                            Your Answer:
                          </p>
                          <div className="bg-slate-950 p-4 rounded-xl text-slate-300 text-sm italic border-l-4 border-slate-600 leading-relaxed">
                            &ldquo;{item.candidate_answer}&rdquo;
                          </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div className="bg-red-500/5 border border-red-500/20 p-5 rounded-2xl">
                            <p className="text-xs font-bold text-red-400 uppercase mb-3 flex items-center gap-2">
                              <AlertCircle size={16} /> Analysis & Feedback
                            </p>
                            <p className="text-sm text-slate-300 leading-relaxed">
                              {item.evaluation}
                            </p>
                          </div>
                          <div className="bg-emerald-500/5 border border-emerald-500/20 p-5 rounded-2xl">
                            <p className="text-xs font-bold text-emerald-400 uppercase mb-3 flex items-center gap-2">
                              <CheckCircle2 size={16} /> Ideal Answer
                            </p>
                            <p className="text-sm text-emerald-100/80 leading-relaxed font-medium">
                              {item.ideal_answer}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-slate-500 p-8 border border-dashed border-slate-700 rounded-2xl">
                Waiting for AI to analyze data...
              </div>
            )}
          </div>
        </div>

        {/* FOOTER */}
        <div className="p-6 border-t border-slate-800 bg-slate-900/80 flex justify-end gap-4">
          <button
            onClick={onClose}
            className="px-6 py-3 font-bold text-slate-400 hover:text-white transition-colors"
          >
            Continue Interview
          </button>
          <button
            onClick={onRetry}
            className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl font-bold flex items-center gap-2 text-white shadow-lg shadow-blue-900/20 transition-all active:scale-95"
          >
            <RotateCcw size={18} /> Start New Interview
          </button>
        </div>
      </div>
    </div>
  );
}
