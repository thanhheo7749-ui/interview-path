/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { Lightbulb, Settings, Camera, RotateCcw, Briefcase, FileCheck2 } from "lucide-react";
import { MicroButton } from "@/components/Interview/MicroButton";
import { ChatBox } from "@/components/Interview/ChatBox";
import { TimerDisplay } from "@/components/Interview/TimerDisplay";
import { InlineCameraWidget } from "@/components/Interview/InlineCameraWidget";
import { PlannerSignals } from "@/components/Interview/PlannerSignals";
import { HintPanel } from "@/components/Interview/HintPanel";
import type { InterviewAnalysis } from "@/hooks/useChat";

interface InterviewStepProps {
  config: any;
  hint: { show: boolean; content: string };
  setHint: (v: any) => void;
  status: string;
  aiText: string;
  userText: string;
  tempText: string;
  isEnglish: boolean;
  questionCount: number;
  timeLeft: number;
  analysis?: InterviewAnalysis | null;
  onMicClick: () => void;
  onHintClick: () => void;
  onSend: (isTimeout: boolean | React.MouseEvent) => void;
  onUserTextChange: (text: string) => void;
  onClearText: () => void;
  onRefreshMic: () => void;
  onFinish: () => void;
  onNewPractice: () => void;
  onOpenSettings: () => void;
  isCameraModeOpen: boolean;
  onToggleCamera: () => void;
  audioElement?: HTMLAudioElement | null;
  isPlayingAudio: boolean;
}

export function InterviewStep({
  config,
  hint,
  setHint,
  status,
  aiText,
  userText,
  tempText,
  isEnglish,
  questionCount,
  timeLeft,
  analysis,
  onMicClick,
  onHintClick,
  onSend,
  onUserTextChange,
  onClearText,
  onRefreshMic,
  onFinish,
  onNewPractice,
  onOpenSettings,
  isCameraModeOpen,
  onToggleCamera,
  audioElement,
  isPlayingAudio,
}: InterviewStepProps) {
  const isStressMode = config.mode === "stress";

  return (
    <div className="flex-1 flex flex-col items-center py-6 px-4 w-full max-w-5xl mx-auto gap-4">
      <div className="w-full flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-theme-border bg-theme-primary p-4">
        <div className="flex items-center gap-2">
          {config.position && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-500/15 border border-blue-500/30 text-blue-300">
              <Briefcase size={12} />
              {config.position}
              {config.company ? ` @ ${config.company}` : ""}
            </span>
          )}
          {config.interviewType === "timed" && (
            <TimerDisplay
              questionCount={questionCount}
              questionLimit={config.questionLimit}
              timeLeft={timeLeft}
            />
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onOpenSettings}
            aria-label="Settings"
            className="p-2 rounded-lg border border-theme-border text-theme-text-secondary hover:text-theme-text hover:bg-theme-surface"
          >
            <Settings size={18} />
          </button>
          <button
            onClick={onToggleCamera}
            aria-label="Toggle camera mode"
            className={`p-2 rounded-lg border ${isCameraModeOpen ? "border-blue-500 text-blue-400 bg-blue-500/10" : "border-theme-border text-theme-text-secondary hover:text-theme-text hover:bg-theme-surface"}`}
          >
            <Camera size={18} />
          </button>
          <button
            onClick={onNewPractice}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-theme-border text-sm font-semibold text-theme-text-secondary hover:text-theme-text hover:bg-theme-surface"
          >
            <RotateCcw size={14} /> New practice
          </button>
          <button
            data-testid="finish-practice"
            onClick={onFinish}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow-md"
          >
            <FileCheck2 size={14} /> Finish & get report
          </button>
        </div>
      </div>

      {isCameraModeOpen && (
        <div className="w-full">
          <InlineCameraWidget
            onClose={onToggleCamera}
            audioElement={audioElement}
            isPlayingAudio={isPlayingAudio}
            isStressMode={isStressMode}
          />
        </div>
      )}

      <div className="relative group z-10 animate-in zoom-in">
        <MicroButton
          status={status}
          onClick={onMicClick}
          langLabel={isEnglish ? "English" : "Vietnamese"}
          isCompact={isCameraModeOpen}
          testId="practice-mic"
        />
        <div className="absolute right-0 -top-12 md:-right-20 md:top-0 flex flex-col gap-4 z-50">
          <button
            onClick={onHintClick}
            aria-label="AI Hint"
            className="w-12 h-12 md:w-14 md:h-14 rounded-full bg-yellow-500/10 flex items-center justify-center hover:scale-110 transition-transform shadow-lg backdrop-blur-sm"
          >
            <Lightbulb className="text-yellow-400 w-5 h-5 md:w-6 md:h-6" />
          </button>
        </div>
        <HintPanel hint={hint} onClose={() => setHint({ show: false, content: "" })} />
      </div>

      <details className="w-full max-w-6xl">
        <summary className="text-xs font-bold text-theme-muted uppercase tracking-widest cursor-pointer select-none">
          AI interviewer signals
        </summary>
        <div className="mt-2">
          <PlannerSignals
            currentFocus={analysis?.next_topic}
            whySelected={analysis?.why_selected}
            nextSkill={analysis?.planner_decision?.next_topic || analysis?.next_topic}
            liveCues={analysis?.live_cues || []}
            analysis={analysis}
          />
        </div>
      </details>

      <ChatBox
        userText={userText}
        tempText={tempText}
        aiText={aiText}
        status={status}
        onUserTextChange={onUserTextChange}
        onSend={() => onSend(false)}
        onClear={onClearText}
        onRefresh={onRefreshMic}
      />
    </div>
  );
}
