/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

import {
  SettingsModal,
  ReportModal,
  GenCVModal,
  ReviewCVModal,
  ResumeConfigModal,
  SubscriptionModal,
  CheckoutModal,
  CVMakeover,
} from "@/components/Modals";
import SupportChatWidget from "@/components/SupportChatWidget";
import { Sidebar } from "@/components/Interview/Sidebar";
import { InterviewLayout } from "@/components/Interview/InterviewLayout";

import { useMicrophone } from "@/hooks/useMicrophone";
import { useChat } from "@/hooks/useChat";
import { useAudioQueue } from "@/hooks/useAudioQueue";
import { useAuth } from "@/context/AuthContext";
import { useSubscription } from "@/context/SubscriptionContext";
import { useInterviewTimer } from "@/hooks/useInterviewTimer";
import { useInterviewState } from "@/hooks/useInterviewState";
import { useInterviewActions } from "@/hooks/useInterviewActions";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { buildInterviewContext } from "@/services/api";

const structuredCvToInterviewText = (cv: any) => {
  const personal = cv?.personal_info || {};
  const skills = Array.isArray(cv?.skills) ? cv.skills.join(", ") : "";
  const experience = Array.isArray(cv?.experience)
    ? cv.experience
        .map(
          (item: any) =>
            `${item.role || ""} at ${item.company || ""}: ${Array.isArray(item.achievements) ? item.achievements.join("; ") : ""}`,
        )
        .join("\n")
    : "";
  const projects = Array.isArray(cv?.projects)
    ? cv.projects
        .map((item: any) => `${item.name || ""}: ${item.description || ""}`)
        .join("\n")
    : "";

  return [
    personal.name,
    personal.title,
    personal.summary,
    skills,
    experience,
    projects,
  ]
    .filter(Boolean)
    .join("\n\n");
};

export default function InterviewRoom() {
  const router = useRouter();
  const { user, logout, isLoading } = useAuth();
  const { upgradeToPro } = useSubscription();
  const [showSubscription, setShowSubscription] = useState(false);
  const [showCheckout, setShowCheckout] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCameraModeOpen, setIsCameraModeOpen] = useState(false);
  const [isBootstrappingContext, setIsBootstrappingContext] = useState(false);
  const [interviewContextError, setInterviewContextError] = useState<string | null>(null);

  const {
    modals,
    toggleModal,
    config,
    setConfig,
    hasStarted,
    setHasStarted,
    isAdmin,
    setIsAdmin,
    interviewHistories,
    setInterviewHistories,
    myProfileData,
    setMyProfileData,
    reportData,
    setReportData,
    hint,
    setHint,
    currentHistoryId,
    setCurrentHistoryId,
    savedReport,
    setSavedReport,
    pendingResumeData,
    setPendingResumeData,
  } = useInterviewState();

  const persistInterviewContext = useCallback((context: Record<string, unknown> | null) => {
    if (!context) {
      sessionStorage.removeItem("interview_context");
      return;
    }
    sessionStorage.setItem("interview_context", JSON.stringify(context));
  }, []);

  const masterCvStructured = myProfileData?.info?.master_cv_structured || null;
  const hasStructuredMasterCv = Boolean(masterCvStructured);
  const hasJd = Boolean(config.jd?.trim());

  const bootstrapInterviewContext = useCallback(async () => {
    if (!hasStructuredMasterCv || !hasJd) {
      persistInterviewContext(null);
      setInterviewContextError(null);
      return true;
    }

    setIsBootstrappingContext(true);
    setInterviewContextError(null);

    try {
      const cvText = structuredCvToInterviewText(masterCvStructured);
      const result = await buildInterviewContext(cvText, config.jd.trim());
      persistInterviewContext((result?.interview_context as Record<string, unknown> | null) || null);
      return true;
    } catch {
      persistInterviewContext(null);
      setInterviewContextError("Could not prepare interview context from your structured Master CV.");
      return false;
    } finally {
      setIsBootstrappingContext(false);
    }
  }, [config.jd, hasJd, hasStructuredMasterCv, masterCvStructured, persistInterviewContext]);

  const masterCvStatus = interviewContextError
    ? interviewContextError
    : isBootstrappingContext
      ? "Preparing interview context from your structured Master CV..."
      : hasStructuredMasterCv
        ? hasJd
          ? "Using your structured Master CV as the default interview context source."
          : "Structured Master CV ready — add a JD to build interview context before starting."
        : "No saved Master CV yet — interview will use JD only.";

  const isEnglish = config.voice?.startsWith("en-");
  const micLang = isEnglish ? "en-US" : "vi-VN";

  const { isPlaying, playAudio, stopAudio, audioElement } = useAudioQueue();

  const {
    status,
    setStatus,
    aiText,
    history,
    sendMessage,
    resetChat,
    interrupt: interruptChat,
    loadSession,
    analysis,
  } = useChat();

  const {
    text: userText,
    setText: setUserText,
    temp: tempText,
    isListening,
    toggleMic,
    resetText,
  } = useMicrophone(micLang);

  const {
    timeLeft,
    setTimeLeft,
    questionCount,
    setQuestionCount,
    resetTimer,
    advanceQuestion,
  } = useInterviewTimer({
    interviewType: config.interviewType,
    timeLimit: config.timeLimit,
    questionLimit: config.questionLimit,
    hasStarted,
    status,
    onTimeUp: () => actions.handleSend(true),
  });

  const actions = useInterviewActions({
    user,
    config,
    setConfig,
    hasStarted,
    setHasStarted,
    modals,
    toggleModal,
    setIsAdmin,
    interviewHistories,
    setInterviewHistories,
    setMyProfileData,
    reportData,
    setReportData,
    hint,
    setHint,
    currentHistoryId,
    setCurrentHistoryId,
    savedReport,
    setSavedReport,
    pendingResumeData,
    setPendingResumeData,
    status,
    setStatus,
    aiText,
    history,
    sendMessage,
    resetChat,
    interruptChat,
    loadSession,
    userText,
    tempText,
    isListening,
    toggleMic,
    resetText,
    playAudio,
    stopAudio,
    timeLeft,
    questionCount,
    setQuestionCount,
    resetTimer,
    advanceQuestion,
  });


  const handleStartTimedInterview = async () => {
    const canStart = await bootstrapInterviewContext();
    if (!canStart) return;
    actions.startTimedInterview();
  };

  useEffect(() => {
    actions.loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    if (config.mode === "stress" && hasStarted) {
      setIsCameraModeOpen(true);
    }
  }, [config.mode, hasStarted]);

  if (!isPlaying && status === "AI Speaking") setStatus("Ready");

  const hasOpenModal = Object.values(modals).some(Boolean) || showSubscription || showCheckout;
  useKeyboardShortcuts({
    onToggleMic: actions.onMicClick,
    onNewInterview: actions.handleNewChat,
    onOpenReport: () => actions.handleOpenReport(false),
    onOpenSettings: () => toggleModal("settings", true),
    onCloseModal: () => {
      if (showCheckout) setShowCheckout(false);
      else if (showSubscription) setShowSubscription(false);
      else {
        const openKey = Object.entries(modals).find(([, v]) => v)?.[0];
        if (openKey) toggleModal(openKey, false);
      }
    },
    hasOpenModal,
  });

  if (isLoading)
    return (
      <div className="h-screen bg-slate-950 flex items-center justify-center text-white">
        Loading...
      </div>
    );

  const interviewLayoutProps = {
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
    onMicClick: actions.onMicClick,
    onHintClick: actions.handleHintClick,
    onSend: actions.handleSend,
    onUserTextChange: setUserText,
    onClearText: resetText,
    onRefreshMic: () => {
      resetText();
      actions.onMicClick();
    },
    startTimedInterview: handleStartTimedInterview,
    isCameraModeOpen,
    onCloseCamera: () => {
      if (config.mode !== "stress") setIsCameraModeOpen(false);
    },
    audioElement,
    isPlayingAudio: isPlaying,
    analysis,
    masterCvAvailable: hasStructuredMasterCv,
    masterCvStatus,
  } as React.ComponentProps<typeof InterviewLayout> & { analysis: typeof analysis };

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      <Sidebar
        user={user}
        myProfileData={myProfileData}
        isAdmin={isAdmin}
        interviewHistories={interviewHistories}
        logout={logout}
        toggleModal={toggleModal}
        handleLoadOldInterview={actions.handleLoadOldInterview}
        handleRetry={actions.handleRetry}
        handleOpenReport={actions.handleOpenReport}
        setInterviewHistories={setInterviewHistories}
        currentHistoryId={currentHistoryId}
        handleNewChat={actions.handleNewChat}
        isGeneratingReport={actions.isGeneratingReport}
        onOpenSubscription={() => setShowSubscription(true)}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onOpenCameraMode={() => setIsCameraModeOpen(true)}
      />

      <InterviewLayout {...interviewLayoutProps} />

      <SettingsModal
        show={modals.settings}
        onClose={() => toggleModal("settings", false)}
        voice={config.voice}
        setVoice={(v: string) => setConfig({ ...config, voice: v })}
        mode={config.mode}
        setMode={(m: string) => setConfig({ ...config, mode: m })}
        jd={config.jd}
        setJd={(j: string) => setConfig({ ...config, jd: j })}
        interviewType={config.interviewType}
        setInterviewType={(t: string) =>
          setConfig({ ...config, interviewType: t })
        }
        questionLimit={config.questionLimit}
        setQuestionLimit={(l: number) =>
          setConfig({ ...config, questionLimit: l })
        }
        timeLimit={config.timeLimit}
        setTimeLimit={(t: number) => setConfig({ ...config, timeLimit: t })}
      />
      <ReportModal
        show={modals.report}
        onClose={() => toggleModal("report", false)}
        result={reportData}
        hasHistory={
          history.trim().length > 0 ||
          (Array.isArray(reportData?.details) && reportData.details.length > 0) ||
          (reportData?.details &&
            typeof reportData.details === "object" &&
            !Array.isArray(reportData.details) &&
            ((Array.isArray(reportData.details.questions) &&
              reportData.details.questions.length > 0) ||
              Object.keys(reportData.details).length > 0))
        }
        onRetry={actions.handleRetry}
      />
      <GenCVModal
        show={modals.cv}
        onClose={() => toggleModal("cv", false)}
        userProfile={myProfileData}
      />
      <ReviewCVModal
        show={modals.review}
        onClose={() => toggleModal("review", false)}
      />
      <CVMakeover
        show={modals.makeover}
        onClose={() => toggleModal("makeover", false)}
        userAvatar={myProfileData?.info?.avatar}
        onEditManually={() => {
          toggleModal("makeover", false);
          toggleModal("cv", true);
        }}
      />
      <ResumeConfigModal
        show={modals.resumeConfig}
        onClose={() => {
          toggleModal("resumeConfig", false);
          setPendingResumeData(null);
        }}
        onConfirm={actions.handleConfirmResume}
        initialConfig={pendingResumeData}
      />
      <SubscriptionModal
        show={showSubscription}
        onClose={() => setShowSubscription(false)}
        onUpgrade={() => {
          setShowSubscription(false);
          setShowCheckout(true);
        }}
      />
      <CheckoutModal
        show={showCheckout}
        onClose={() => setShowCheckout(false)}
        onSuccess={upgradeToPro}
      />
      <SupportChatWidget />
    </div>
  );
}
