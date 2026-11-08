/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { safeRedirect } from "@/lib/safeRedirect";

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
import { PracticeTopBar } from "@/components/Interview/steps/PracticeTopBar";
import { SetupStep } from "@/components/Interview/steps/SetupStep";
import { InterviewStep } from "@/components/Interview/steps/InterviewStep";
import { ReportStep } from "@/components/Interview/steps/ReportStep";
import { PrepareMenu } from "@/components/Interview/PrepareMenu";
import { PracticeHistoryList } from "@/components/Interview/PracticeHistoryList";
import { PRACTICE_STEP_FLOW } from "@/lib/features";

import { useMicrophone } from "@/hooks/useMicrophone";
import { useChat } from "@/hooks/useChat";
import { useAudioQueue } from "@/hooks/useAudioQueue";
import { useAuth } from "@/context/AuthContext";
import { useSubscription } from "@/context/SubscriptionContext";
import { useInterviewTimer } from "@/hooks/useInterviewTimer";
import { useInterviewState } from "@/hooks/useInterviewState";
import { useInterviewActions } from "@/hooks/useInterviewActions";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { usePracticePrefill } from "@/hooks/usePracticePrefill";
import { savePracticeSettings } from "@/lib/practiceSettingsStorage";
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
  return (
    <Suspense fallback={null}>
      <InterviewRoomInner />
    </Suspense>
  );
}

function InterviewRoomInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextHref = safeRedirect(searchParams.get("next"), "", typeof window !== "undefined" ? window.location.origin : "");
  const applicationId = searchParams.get("applicationId");
  const { user, logout, isLoading } = useAuth();
  const { upgradeToPro } = useSubscription();
  const [showSubscription, setShowSubscription] = useState(false);
  const [showCheckout, setShowCheckout] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCameraModeOpen, setIsCameraModeOpen] = useState(false);
  const [cameraMode, setCameraMode] = useState(false);
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

  const autoFilledPositionRef = useRef(false);
  useEffect(() => {
    if (autoFilledPositionRef.current || !masterCvStructured || applicationId) return;
    autoFilledPositionRef.current = true;
    const title = masterCvStructured?.personal_info?.title?.trim();
    if (title && !config.position.trim()) {
      setConfig({ ...config, position: title });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [masterCvStructured]);

  const { prefillNotice, clearPrefill } = usePracticePrefill({
    config,
    setConfig,
    interviewHistories,
    applicationId,
    isLoggedIn: Boolean(user),
  });

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
    savePracticeSettings(config);
    actions.startTimedInterview();
  };

  const handleStart = async () => {
    const canStart = await bootstrapInterviewContext();
    if (!canStart) return;
    savePracticeSettings(config);
    if (config.interviewType === "timed") actions.startTimedInterview();
    else actions.startFreeInterview();
    if (cameraMode) setIsCameraModeOpen(true);
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

  const step: "setup" | "interview" | "report" = modals.report
    ? "report"
    : hasStarted
      ? "interview"
      : "setup";

  const stepScrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    stepScrollRef.current?.scrollTo({ top: 0 });
  }, [step]);

  if (isLoading)
    return (
      <div className="h-screen bg-slate-950 flex items-center justify-center text-white">
        Loading...
      </div>
    );

  const hasReportHistory =
    history.trim().length > 0 ||
    (Array.isArray(reportData?.details) && reportData.details.length > 0) ||
    (reportData?.details &&
      typeof reportData.details === "object" &&
      !Array.isArray(reportData.details) &&
      ((Array.isArray(reportData.details.questions) &&
        reportData.details.questions.length > 0) ||
        Object.keys(reportData.details).length > 0));

  const interviewLayoutProps = {
    config,
    setConfig,
    prefillNotice,
    onClearPrefill: clearPrefill,
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
      {nextHref && (
        <Link
          href={nextHref}
          className="fixed top-3 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-lg"
        >
          Vào phỏng vấn tuyển dụng thật →
        </Link>
      )}
      {PRACTICE_STEP_FLOW ? (
        <div
          ref={stepScrollRef}
          className="flex-1 flex flex-col overflow-y-auto custom-scrollbar bg-theme-secondary"
        >
          <PracticeTopBar
            step={step}
            right={
              <PrepareMenu
                user={user}
                toggleModal={toggleModal}
                onOpenCameraMode={() => setIsCameraModeOpen(true)}
              />
            }
          />

          {step === "setup" && (
            <SetupStep
              config={config}
              setConfig={setConfig}
              onStart={handleStart}
              masterCvAvailable={hasStructuredMasterCv}
              masterCvStatus={masterCvStatus}
              prefillNotice={prefillNotice}
              onClearPrefill={clearPrefill}
              cameraMode={cameraMode}
              setCameraMode={setCameraMode}
              aside={
                <PracticeHistoryList
                  user={user}
                  interviewHistories={interviewHistories}
                  setInterviewHistories={setInterviewHistories}
                  currentHistoryId={currentHistoryId}
                  handleLoadOldInterview={actions.handleLoadOldInterview}
                  handleRetry={actions.handleRetry}
                />
              }
            />
          )}

          {step === "interview" && (
            <InterviewStep
              config={config}
              hint={hint}
              setHint={setHint}
              status={status}
              aiText={aiText}
              userText={userText}
              tempText={tempText}
              isEnglish={isEnglish}
              questionCount={questionCount}
              timeLeft={timeLeft}
              analysis={analysis}
              onMicClick={actions.onMicClick}
              onHintClick={actions.handleHintClick}
              onSend={actions.handleSend}
              onUserTextChange={setUserText}
              onClearText={resetText}
              onRefreshMic={() => {
                resetText();
                actions.onMicClick();
              }}
              onFinish={() => actions.handleOpenReport(false)}
              onNewPractice={actions.handleNewChat}
              onOpenSettings={() => toggleModal("settings", true)}
              isCameraModeOpen={isCameraModeOpen}
              onToggleCamera={() => setIsCameraModeOpen((v) => !v)}
              audioElement={audioElement}
              isPlayingAudio={isPlaying}
            />
          )}

          {step === "report" && (
            <ReportStep
              result={reportData}
              hasHistory={hasReportHistory}
              isGenerating={actions.isGeneratingReport}
              nextHref={nextHref}
              onContinue={() => toggleModal("report", false)}
              onPracticeAgain={actions.handleRetry}
              onBack={() => toggleModal("report", false)}
            />
          )}
        </div>
      ) : (
        <>
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
        </>
      )}

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
        show={!PRACTICE_STEP_FLOW && modals.report}
        onClose={() => toggleModal("report", false)}
        result={reportData}
        hasHistory={hasReportHistory}
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
