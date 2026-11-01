/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import {
  Briefcase,
  Play,
  ShieldCheck,
  Sparkles,
  Building2,
  CheckCircle2,
  Target,
} from "lucide-react";
import toast from "react-hot-toast";

interface SetupFormProps {
  config: any;
  setConfig: (c: any) => void;
  onStart: () => void;
  masterCvAvailable: boolean;
  masterCvStatus: string;
}

export const ENTERPRISE_DEMO_PRESETS = [
  {
    id: "k_tech_backend",
    badge: "🇰🇷 K-Tech Enterprise (Recommended)",
    position: "Backend Developer (Python / FastAPI)",
    company: "K-Tech Partner Enterprise (Cobi Tower II)",
    mode: "k_culture_fit",
    voice: "en-US-AndrewMultilingualNeural",
    matchScore: 78,
    matchedStrengths: ["Python", "FastAPI", "Docker", "REST APIs"],
    priorityGaps: [
      "Redis Distributed Caching",
      "High-Concurrency System Design",
      "K-Culture Ownership & STAR",
    ],
    jd: "We need Python, FastAPI, REST APIs, Redis Caching, Docker, System Design, and strong Ownership, Integrity, and Structured STAR Teamwork for a Korean global engineering team.",
  },
  {
    id: "fullstack_ai",
    badge: "🚀 Full-Stack AI Engineer",
    position: "Full-Stack AI Engineer (Next.js / Python)",
    company: "LIKELION Tech Innovation Lab",
    mode: "technical",
    voice: "en-US-AndrewMultilingualNeural",
    matchScore: 82,
    matchedStrengths: ["Next.js", "TypeScript", "Python", "FastAPI"],
    priorityGaps: ["RAG Graph Retrieval", "Prompt Guardrails", "Latency Optimization"],
    jd: "Required: Next.js, TypeScript, Python, FastAPI, RAG Architecture, Prompt Engineering, Docker, and agile problem-solving.",
  },
  {
    id: "it_ba_pm",
    badge: "📊 IT Business Analyst / AI PM",
    position: "IT Business Analyst / AI PM",
    company: "KOCHAM Enterprise Solutions",
    mode: "behavioral",
    voice: "en-US-AndrewMultilingualNeural",
    matchScore: 74,
    matchedStrengths: ["Agile Scrum", "SQL", "Stakeholder Alignment"],
    priorityGaps: ["AI ROI Modeling", "Cross-Border Korean-VN Communication"],
    jd: "Must have Requirements Analysis, Stakeholder Communication, Agile Scrum, SQL, Data Analytics, and Ownership mindset.",
  },
];

export function SetupForm({
  config,
  setConfig,
  onStart,
  masterCvAvailable,
  masterCvStatus,
}: SetupFormProps) {
  const handleStart = () => {
    if (config.interviewType === "timed" && !config.position.trim()) {
      toast.error("Please enter the position you're applying for!");
      return;
    }
    onStart();
  };

  const applyPreset = (preset: (typeof ENTERPRISE_DEMO_PRESETS)[number]) => {
    setConfig({
      ...config,
      position: preset.position,
      company: preset.company,
      mode: preset.mode,
      voice: preset.voice,
      jd: preset.jd,
    });
    toast.success(`Loaded preset: ${preset.position}`);
  };

  const activePreset =
    ENTERPRISE_DEMO_PRESETS.find(
      (p) => p.position === config.position && p.company === config.company,
    ) || ENTERPRISE_DEMO_PRESETS[0];

  return (
    <div className="mt-4 bg-theme-primary/90 p-6 md:p-8 rounded-2xl border border-theme-border w-full max-w-3xl shadow-xl animate-in zoom-in flex flex-col gap-5 z-20">
      <div className="text-center">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-xs font-bold text-blue-400 mb-2">
          <Building2 size={13} /> B2B AI Pre-Screening &amp; Candidate Readiness Setup
        </div>
        <h2 className="text-2xl font-black text-white flex items-center justify-center gap-2">
          <Briefcase className="text-blue-400" /> Interview Context Setup
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          Ground the AI Question Planner with CV, Job Description, and Enterprise Culture Fit criteria
        </p>
      </div>

      {/* 1-Click Enterprise Demo Presets */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles size={13} /> 1-Click Enterprise Demo Presets
          </span>
          <span className="text-[11px] text-slate-400">
            Instant setup for 2-minute video demo
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {ENTERPRISE_DEMO_PRESETS.map((preset) => {
            const isSelected =
              config.position === preset.position && config.company === preset.company;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset)}
                className={`text-left p-3 rounded-xl border transition-all ${
                  isSelected
                    ? "bg-blue-600/20 border-blue-500 text-white shadow-md"
                    : "bg-theme-secondary/70 border-theme-border/60 text-slate-300 hover:border-blue-500/50 hover:bg-theme-secondary"
                }`}
              >
                <div className="text-xs font-bold text-cyan-300 mb-1 truncate">
                  {preset.badge}
                </div>
                <div className="text-xs font-semibold text-white truncate">
                  {preset.position}
                </div>
                <div className="text-[11px] text-slate-400 truncate mt-0.5">
                  {preset.company}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Live CV vs JD Gap Analysis Preview */}
      {config.jd && (
        <div className="rounded-2xl border border-cyan-500/30 bg-cyan-950/20 p-4 space-y-3 animate-in fade-in">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-1.5">
              <Target size={14} /> AI Context Seed: CV vs. JD Gap Analysis
            </span>
            <span className="text-xs font-black text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-0.5 rounded-full">
              Initial JD Match: {activePreset.matchScore}%
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl bg-slate-900/70 border border-slate-800 p-3">
              <div className="font-bold text-emerald-400 mb-1.5 flex items-center gap-1">
                <CheckCircle2 size={12} /> Matched CV Strengths
              </div>
              <div className="flex flex-wrap gap-1.5">
                {activePreset.matchedStrengths.map((s) => (
                  <span
                    key={s}
                    className="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-200 font-medium"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-xl bg-slate-900/70 border border-slate-800 p-3">
              <div className="font-bold text-amber-400 mb-1.5 flex items-center gap-1">
                <Sparkles size={12} /> Priority Skill Gaps (AI Will Probe)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {activePreset.priorityGaps.map((g) => (
                  <span
                    key={g}
                    className="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/25 text-amber-200 font-medium"
                  >
                    {g}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            Position *
          </label>
          <input
            className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text focus:border-blue-600 outline-none text-sm"
            placeholder="E.g.: Backend Dev..."
            value={config.position}
            onChange={(e) => setConfig({ ...config, position: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            Company / Enterprise
          </label>
          <input
            className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text focus:border-blue-600 outline-none text-sm"
            placeholder="E.g.: LIKELION / Samsung..."
            value={config.company}
            onChange={(e) => setConfig({ ...config, company: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            Evaluation Rubric Mode
          </label>
          <select
            className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text focus:border-blue-600 outline-none text-sm"
            value={config.mode}
            onChange={(e) => setConfig({ ...config, mode: e.target.value })}
          >
            <option value="k_culture_fit">
              🇰🇷 Korean / FDI Enterprise (Tech + Ownership)
            </option>
            <option value="technical">💻 Technical, In-depth</option>
            <option value="behavioral">🤝 Behavioral (STAR Situational)</option>
            <option value="general">💬 Friendly, General</option>
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
          Job Description (JD) &amp; Core Competencies
        </label>
        <textarea
          className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text h-20 focus:border-blue-600 outline-none custom-scrollbar text-sm leading-relaxed"
          placeholder="Paste the JD content and cultural expectations here..."
          value={config.jd}
          onChange={(e) => setConfig({ ...config, jd: e.target.value })}
        />
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs rounded-xl bg-theme-secondary/60 border border-theme-border px-4 py-3">
        <div className="text-theme-text-secondary">
          {masterCvStatus ||
            (masterCvAvailable
              ? "Using your structured Master CV as the default interview context source."
              : "No saved Master CV yet — interview will use JD + live responses.")}
        </div>
        <div className="inline-flex items-center gap-1.5 text-emerald-400 font-semibold shrink-0 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
          <ShieldCheck size={14} /> 2 PII Fields Auto-Masked (Email, Phone)
        </div>
      </div>

      <button
        id="tour-step-start"
        onClick={handleStart}
        className="mt-1 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-black py-4 px-8 rounded-xl text-lg shadow-lg shadow-blue-900/30 active:scale-95 transition-all flex items-center justify-center gap-3"
      >
        <Play fill="currentColor" size={20} /> START CONTEXT-AWARE INTERVIEW
      </button>
    </div>
  );
}
