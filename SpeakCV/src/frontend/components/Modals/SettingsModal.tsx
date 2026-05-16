/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useState, useEffect } from "react";
import { X, Settings2, Sliders, Clock, Target, Briefcase } from "lucide-react";
import { getJdTemplates } from "@/services/api";

export default function SettingsModal({
  show,
  onClose,
  voice,
  setVoice,
  mode,
  setMode,
  jd,
  setJd,
  interviewType,
  setInterviewType,
  questionLimit,
  setQuestionLimit,
  timeLimit,
  setTimeLimit,
}: any) {
  const [templates, setTemplates] = useState<any[]>([]);

  useEffect(() => {
    if (show) {
      getJdTemplates()
        .then((data) => setTemplates(data.templates || []))
        .catch((err) => console.log("Error loading JD templates:", err));
    }
  }, [show]);

  const handleSelectTemplate = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedId = parseInt(e.target.value);
    const selectedTemplate = templates.find((t) => t.id === selectedId);
    if (selectedTemplate) {
      setJd(selectedTemplate.description);
    } else {
      setJd("");
    }
  };

  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Interview Settings">
      <div className="bg-white w-full max-w-xl rounded-3xl border border-slate-200 shadow-xl overflow-hidden animate-in zoom-in-95">
        <div className="flex justify-between items-center px-6 py-4 border-b border-slate-200 bg-slate-50">
          <h2 className="text-xl font-bold flex items-center gap-2 text-slate-900">
            <Settings2 className="text-blue-400" /> Interview Settings
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-full text-slate-500 hover:text-slate-900 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto custom-scrollbar">
          {/* MODE SETTINGS */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Target size={16} /> Interview Format
            </h3>
            <div className="flex gap-3">
              <button
                onClick={() => setInterviewType("free")}
                className={`flex-1 py-3 px-4 rounded-xl border font-bold transition-all ${
                  interviewType === "free"
                    ? "bg-blue-600/20 border-blue-500 text-blue-400"
                    : "bg-white border-slate-200 text-slate-600 hover:border-slate-400"
                }`}
              >
                Free
              </button>
              <button
                onClick={() => setInterviewType("timed")}
                className={`flex-1 py-3 px-4 rounded-xl border font-bold transition-all ${
                  interviewType === "timed"
                    ? "bg-blue-50 border-blue-500 text-blue-700"
                    : "bg-white border-slate-200 text-slate-600 hover:border-slate-400"
                }`}
              >
                Stress (Timed)
              </button>
            </div>

            {/* Timed mode */}
            {interviewType === "timed" && (
              <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 space-y-5 animate-in slide-in-from-top-2">
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm font-medium text-slate-700">
                      Question Limit
                    </label>
                    <span className="text-blue-600 font-bold">
                      {questionLimit} questions
                    </span>
                  </div>
                  <input
                    type="range"
                    min="3"
                    max="15"
                    value={questionLimit}
                    onChange={(e) => setQuestionLimit(parseInt(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm font-medium text-slate-700 flex items-center gap-1">
                      <Clock size={14} /> Time per Question
                    </label>
                    <span className="text-blue-600 font-bold">
                      {timeLimit}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="30"
                    max="300"
                    step="30"
                    value={timeLimit}
                    onChange={(e) => setTimeLimit(parseInt(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                </div>
              </div>
            )}
          </div>

          <hr className="border-slate-200" />

          {/* AI CONFIGURATION */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Sliders size={16} /> AI Configuration
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-slate-500 mb-1 block">
                  AI Voice
                </label>
                <select
                  className="w-full bg-white border border-slate-200 p-3 rounded-xl text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200"
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                >
                  <option value="en-US-AndrewMultilingualNeural">
                    English (Andrew - Male)
                  </option>
                  <option value="vi-VN-HoaiMyNeural">
                    Vietnamese (Hoài My - Female)
                  </option>
                  <option value="vi-VN-NamMinhNeural">
                    Vietnamese (Nam Minh - Male)
                  </option>
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-500 mb-1 block">
                  Interview Style
                </label>
                <select
                  className="w-full bg-white border border-slate-200 p-3 rounded-xl text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="general">Friendly, General</option>
                  <option value="technical">Technical, In-depth</option>
                  <option value="behavioral">Behavioral (Situational)</option>
                </select>
              </div>
            </div>

            <div className="bg-white border border-slate-200 p-4 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-bold text-slate-700 flex items-center gap-2">
                  <Briefcase size={16} className="text-yellow-500" />
                  Job Description (JD)
                </label>
              </div>

              {/* JD template dropdown */}
              <select
                className="w-full bg-white border border-slate-200 p-2.5 rounded-lg text-sm text-slate-700 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200 cursor-pointer"
                onChange={handleSelectTemplate}
                defaultValue=""
              >
                <option value="" disabled>
                  -- Select a JD template (Optional) --
                </option>
                <option value="">Custom Input</option>
                {templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.title}
                  </option>
                ))}
              </select>

              {/* Textarea */}
              <textarea
                className="w-full bg-white border border-slate-200 p-3 rounded-lg text-slate-900 h-32 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200 custom-scrollbar text-sm leading-relaxed placeholder:text-slate-400"
                placeholder="Paste JD content here or select from templates above for more relevant AI questions..."
                value={jd}
                onChange={(e) => setJd(e.target.value)}
              />
            </div>
          </div>
        </div>
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-xl text-white font-bold transition-all shadow-md"
          >
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
