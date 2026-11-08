/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Lightbulb,
  Menu,
  Sun,
  Moon,
  Briefcase,
} from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

import { MicroButton } from "@/components/Interview/MicroButton";
import { ChatBox } from "@/components/Interview/ChatBox";
import { SetupForm } from "@/components/Interview/SetupForm";
import { TimerDisplay } from "@/components/Interview/TimerDisplay";
import { InlineCameraWidget } from "@/components/Interview/InlineCameraWidget";
import { PlannerSignals } from "@/components/Interview/PlannerSignals";
import { HintPanel } from "@/components/Interview/HintPanel";
import type { InterviewAnalysis } from "@/hooks/useChat";

interface InterviewLayoutProps {
  config: any;
  setConfig: (c: any) => void;
  hasStarted: boolean;
  hint: { show: boolean; content: string };
  setHint: (v: any) => void;
  status: string;
  aiText: string;
  userText: string;
  tempText: string;
  isEnglish: boolean;
  isSidebarOpen: boolean;
  setIsSidebarOpen: (v: boolean) => void;
  questionCount: number;
  timeLeft: number;
  analysis?: InterviewAnalysis | null;
  masterCvAvailable: boolean;
  masterCvStatus: string;
  prefillNotice?: { label: string } | null;
  onClearPrefill?: () => void;
  // Actions
  onMicClick: () => void;
  onHintClick: () => void;
  onSend: (isTimeout: boolean | React.MouseEvent) => void;
  onUserTextChange: (text: string) => void;
  onClearText: () => void;
  onRefreshMic: () => void;
  startTimedInterview: () => void;
  isCameraModeOpen: boolean;
  onCloseCamera: () => void;
  audioElement?: HTMLAudioElement | null;
  isPlayingAudio: boolean;
}

export function InterviewLayout({
  config,
  setConfig,
  hasStarted,
  hint,
  setHint,
  status,
  aiText,
  userText,
  tempText,
  isEnglish,
  isSidebarOpen,
  setIsSidebarOpen,
  questionCount,
  timeLeft,
  analysis,
  masterCvAvailable,
  masterCvStatus,
  prefillNotice,
  onClearPrefill,
  onMicClick,
  onHintClick,
  onSend,
  onUserTextChange,
  onClearText,
  onRefreshMic,
  startTimedInterview,
  isCameraModeOpen,
  onCloseCamera,
  audioElement,
  isPlayingAudio,
}: InterviewLayoutProps) {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [showContextSetup, setShowContextSetup] = useState(false);

  const isStressMode = config.mode === "stress";

  const shouldShowSetup =
    (config.interviewType === "timed" && !hasStarted) || showContextSetup;

  return (
    <main className="flex-1 flex flex-col items-center justify-between py-6 px-6 relative bg-theme-secondary overflow-y-auto custom-scrollbar">
      {/* Theme Toggle - Top Right */}
      <button
        onClick={toggleTheme}
        className="absolute top-4 right-4 z-20 p-2.5 bg-theme-surface/80 border border-theme-border rounded-xl text-theme-text-secondary hover:text-yellow-400 backdrop-blur-sm shadow-lg transition-all hover:scale-105"
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        title={theme === "dark" ? "Light mode" : "Dark mode"}
      >
        {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
      </button>

      {/* Mobile Hamburger Menu */}
      <button
        onClick={() => setIsSidebarOpen(true)}
        aria-label="Open menu"
        className={`md:hidden absolute top-4 left-4 z-20 p-2 bg-theme-surface/80 border border-theme-border rounded-lg text-theme-text-secondary hover:text-theme-text backdrop-blur-sm shadow-lg transition-opacity duration-300 ${isSidebarOpen ? "opacity-0 pointer-events-none" : "opacity-100"}`}
      >
        <Menu size={20} />
      </button>

      <header className="text-center z-10 flex flex-col items-center gap-2">
        <h1
          className="text-5xl md:text-6xl font-black italic bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent cursor-pointer"
          onClick={() => router.push("/")}
        >
          SpeakCV
        </h1>

        {/* Active context bar */}
        <div className="flex flex-wrap items-center justify-center gap-2 mt-1">
          {config.position && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-500/15 border border-blue-500/30 text-blue-300">
              <Briefcase size={12} />
              {config.position}
              {config.company ? ` @ ${config.company}` : ""}
            </span>
          )}

          <button
            type="button"
            onClick={() => setShowContextSetup((prev) => !prev)}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-theme-surface/80 hover:bg-theme-surface border border-theme-border text-theme-text-secondary hover:text-white transition-all"
          >
            {showContextSetup ? "Close Context Setup" : "🎯 Context & JD Setup"}
          </button>
        </div>

        {config.interviewType === "timed" && hasStarted && (
          <TimerDisplay
            questionCount={questionCount}
            questionLimit={config.questionLimit}
            timeLeft={timeLeft}
          />
        )}
      </header>

      {shouldShowSetup ? (
        <SetupForm
          config={config}
          setConfig={setConfig}
          onStart={() => {
            setShowContextSetup(false);
            startTimedInterview();
          }}
          masterCvAvailable={masterCvAvailable}
          masterCvStatus={masterCvStatus}
          prefillNotice={prefillNotice}
          onClearPrefill={onClearPrefill}
        />
      ) : (
        <>
          {isCameraModeOpen && (
            <div className="w-full px-4 z-20">
              <InlineCameraWidget
                onClose={onCloseCamera}
                audioElement={audioElement}
                isPlayingAudio={isPlayingAudio}
                isStressMode={isStressMode}
              />
            </div>
          )}
          <div
            className={`relative group z-10 animate-in zoom-in transition-all ${
              isCameraModeOpen ? "mt-2 mb-6" : "mt-2 mb-8 md:mt-6"
            }`}
          >
            <MicroButton
              status={status}
              onClick={onMicClick}
              langLabel={isEnglish ? "English" : "Vietnamese"}
              isCompact={isCameraModeOpen}
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

          <PlannerSignals
            currentFocus={analysis?.next_topic}
            whySelected={analysis?.why_selected}
            nextSkill={analysis?.planner_decision?.next_topic || analysis?.next_topic}
            liveCues={analysis?.live_cues || []}
            analysis={analysis}
          />

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
        </>
      )}
    </main>
  );
}
