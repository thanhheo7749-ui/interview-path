/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { X, Trophy, Mic, RotateCcw } from "lucide-react";
import { LEGACY_B2C } from "@/lib/features";
import { ReportContent } from "@/components/Modals/ReportContent";

// === MAIN REPORT MODAL ===
export default function ReportModal({
  show,
  onClose,
  result,
  onRetry,
  hasHistory,
  voiceMetrics,
}: any) {
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
          <ReportContent result={result} voiceMetrics={voiceMetrics} />
        </div>

        {/* FOOTER */}
        <div className="p-6 border-t border-slate-800 bg-slate-900/80 flex justify-end gap-4">
          <button
            onClick={onClose}
            className="px-6 py-3 font-bold text-slate-400 hover:text-white transition-colors"
          >
            Continue Interview
          </button>
          {LEGACY_B2C && (
            <button
              onClick={onRetry}
              className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl font-bold flex items-center gap-2 text-white shadow-lg shadow-blue-900/20 transition-all active:scale-95"
            >
              <RotateCcw size={18} /> Start New Interview
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
