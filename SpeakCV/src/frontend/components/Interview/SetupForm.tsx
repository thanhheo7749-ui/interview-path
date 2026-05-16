/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { Briefcase, Play } from "lucide-react";
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
    <div className="mt-8 bg-theme-primary/90 p-8 rounded-2xl border border-theme-border w-full max-w-2xl shadow-xl animate-in zoom-in flex flex-col gap-5">
      <div className="text-center mb-2">
        <h2 className="text-2xl font-black text-white flex items-center justify-center gap-2">
          <Briefcase className="text-blue-400" /> Interview Setup
        </h2>
        <p className="text-slate-400 text-sm mt-2">
          Provide context for the AI to ask the most relevant questions
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            Position *
          </label>
          <input
            className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text focus:border-blue-600 outline-none"
            placeholder="E.g.: Frontend Dev..."
            value={config.position}
            onChange={(e) => setConfig({ ...config, position: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            Company Name
          </label>
          <input
            className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text focus:border-blue-600 outline-none"
            placeholder="E.g.: Google..."
            value={config.company}
            onChange={(e) => setConfig({ ...config, company: e.target.value })}
          />
        </div>
      </div>
      <div>
        <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
          Job Description (JD)
        </label>
        <textarea
          className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text h-24 focus:border-blue-600 outline-none custom-scrollbar"
          placeholder="Paste the JD content here..."
          value={config.jd}
          onChange={(e) => setConfig({ ...config, jd: e.target.value })}
        />
      </div>
      <div className="text-sm text-theme-text-secondary rounded-xl bg-theme-secondary/60 border border-theme-border px-4 py-3">
        {masterCvStatus ||
          (masterCvAvailable
            ? "Using your structured Master CV as the default interview context source."
            : "No saved Master CV yet — interview will use JD only.")}
      </div>
      <button
        id="tour-step-start"
        onClick={handleStart}
        className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-black py-4 px-8 rounded-xl text-lg shadow-md active:scale-95 transition-all flex items-center justify-center gap-3"
      >
        <Play fill="currentColor" size={20} /> START INTERVIEW!
      </button>
    </div>
  );
}
