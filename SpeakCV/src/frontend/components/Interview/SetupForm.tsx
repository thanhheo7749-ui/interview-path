/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { Briefcase, Play, Building2 } from "lucide-react";
import toast from "react-hot-toast";

interface SetupFormProps {
  config: any;
  setConfig: (c: any) => void;
  onStart: () => void;
  masterCvAvailable: boolean;
  masterCvStatus: string;
}

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
