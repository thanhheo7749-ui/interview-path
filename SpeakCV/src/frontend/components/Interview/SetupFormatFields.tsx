/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { Clock, Target } from "lucide-react";

interface SetupFormatFieldsProps {
  config: any;
  setConfig: (c: any) => void;
}

export function SetupFormatFields({ config, setConfig }: SetupFormatFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            Interview Format
          </label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setConfig({ ...config, interviewType: "free" })}
              className={`flex-1 py-3 px-4 rounded-xl border font-bold text-sm transition-all ${
                config.interviewType === "free"
                  ? "bg-blue-600/20 border-blue-500 text-blue-400"
                  : "bg-theme-secondary border-theme-border text-theme-text-secondary hover:border-slate-400"
              }`}
            >
              Free
            </button>
            <button
              type="button"
              onClick={() => setConfig({ ...config, interviewType: "timed" })}
              className={`flex-1 py-3 px-4 rounded-xl border font-bold text-sm transition-all ${
                config.interviewType === "timed"
                  ? "bg-blue-600/20 border-blue-500 text-blue-400"
                  : "bg-theme-secondary border-theme-border text-theme-text-secondary hover:border-slate-400"
              }`}
            >
              Stress (Timed)
            </button>
          </div>
        </div>
        <div>
          <label className="text-xs font-bold text-slate-400 uppercase block mb-2">
            AI Voice
          </label>
          <select
            className="w-full bg-theme-secondary border border-theme-border p-3 rounded-xl text-theme-text focus:border-blue-600 outline-none text-sm"
            value={config.voice}
            onChange={(e) => setConfig({ ...config, voice: e.target.value })}
          >
            <option value="en-US-AndrewMultilingualNeural">English (Andrew - Male)</option>
            <option value="vi-VN-HoaiMyNeural">Vietnamese (Hoài My - Female)</option>
            <option value="vi-VN-NamMinhNeural">Vietnamese (Nam Minh - Male)</option>
          </select>
        </div>
      </div>

      {config.interviewType === "timed" && (
        <div className="bg-theme-secondary/60 p-5 rounded-xl border border-theme-border space-y-5 animate-in slide-in-from-top-2">
          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm font-medium text-theme-text-secondary flex items-center gap-1">
                <Target size={14} /> Question Limit
              </label>
              <span className="text-blue-400 font-bold">{config.questionLimit} questions</span>
            </div>
            <input
              type="range"
              min="3"
              max="15"
              value={config.questionLimit}
              onChange={(e) => setConfig({ ...config, questionLimit: parseInt(e.target.value) })}
              className="w-full accent-blue-600"
            />
          </div>
          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm font-medium text-theme-text-secondary flex items-center gap-1">
                <Clock size={14} /> Time per Question
              </label>
              <span className="text-blue-400 font-bold">{config.timeLimit}s</span>
            </div>
            <input
              type="range"
              min="30"
              max="300"
              step="30"
              value={config.timeLimit}
              onChange={(e) => setConfig({ ...config, timeLimit: parseInt(e.target.value) })}
              className="w-full accent-blue-600"
            />
          </div>
        </div>
      )}
    </>
  );
}
