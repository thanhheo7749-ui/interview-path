/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import Link from "next/link";
import { Trophy, Mic, RotateCcw, ArrowRight } from "lucide-react";
import { ReportContent } from "@/components/Modals/ReportContent";

interface ReportStepProps {
  result: any;
  hasHistory: boolean;
  isGenerating: boolean;
  nextHref: string;
  onContinue: () => void;
  onPracticeAgain: () => void;
  onBack: () => void;
}

export function ReportStep({
  result,
  hasHistory,
  isGenerating,
  nextHref,
  onContinue,
  onPracticeAgain,
  onBack,
}: ReportStepProps) {
  if (!hasHistory) {
    return (
      <div
        data-testid="practice-report"
        className="w-full max-w-lg mx-auto my-8 rounded-2xl border border-theme-border bg-theme-primary p-10 flex flex-col items-center text-center"
      >
        <div className="w-24 h-24 bg-blue-500/10 rounded-full flex items-center justify-center mb-6">
          <Mic size={40} className="text-blue-400" />
        </div>
        <h2 className="text-2xl font-bold text-theme-text mb-3">No Interview Started</h2>
        <p className="text-theme-text-secondary mb-8 leading-relaxed">
          Start speaking with the AI interviewer first, then come back here for your report.
        </p>
        <button
          onClick={onBack}
          className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl font-bold text-white w-full transition-all active:scale-95"
        >
          Back to practice
        </button>
      </div>
    );
  }

  if (isGenerating) {
    return (
      <div
        data-testid="practice-report"
        className="w-full max-w-lg mx-auto my-8 rounded-2xl border border-theme-border bg-theme-primary p-10 flex flex-col items-center text-center"
      >
        <div className="w-16 h-16 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mb-6" />
        <h2 className="text-xl font-bold text-theme-text">Scoring your interview...</h2>
        <p className="text-theme-text-secondary mt-2">This takes a few seconds.</p>
      </div>
    );
  }

  return (
    <div data-testid="practice-report" className="w-full max-w-5xl mx-auto my-6 px-4">
      <div className="rounded-2xl border border-theme-border bg-theme-primary p-5 mb-4 flex items-center gap-3">
        <Trophy className="text-yellow-500" size={24} />
        <h2 className="text-lg font-black text-theme-text tracking-wide">Interview Report</h2>
      </div>

      <ReportContent result={result} />

      <div className="rounded-2xl border border-theme-border bg-theme-primary p-5 mt-4 flex flex-wrap items-center justify-end gap-3">
        <button
          onClick={onContinue}
          data-testid="report-continue"
          className="px-6 py-3 font-bold text-theme-text-secondary hover:text-theme-text transition-colors"
        >
          Continue
        </button>
        <button
          onClick={onPracticeAgain}
          data-testid="report-practice-again"
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl font-bold text-white shadow-lg transition-all active:scale-95"
        >
          <RotateCcw size={18} /> Practice again
        </button>
        {nextHref && (
          <Link
            href={nextHref}
            data-testid="report-real-interview"
            className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 px-8 py-3 rounded-xl font-bold text-white shadow-lg transition-all active:scale-95"
          >
            Vào phỏng vấn tuyển dụng thật <ArrowRight size={16} />
          </Link>
        )}
      </div>
    </div>
  );
}
