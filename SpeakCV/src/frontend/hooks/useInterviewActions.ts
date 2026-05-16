/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useState } from "react";
import toast from "react-hot-toast";

import {
  endInterview,
  getHint,
  getMyProfile,
  getAdminDashboard,
  getHistory,
  updateInterviewConfig,
} from "@/services/api";

interface UseInterviewActionsParams {
  user: string | null;
  config: any;
  setConfig: (c: any) => void;
  hasStarted: boolean;
  setHasStarted: (v: boolean) => void;
  modals: any;
  toggleModal: (key: string, val: boolean) => void;
  setIsAdmin: (v: boolean) => void;
  interviewHistories: any[];
  setInterviewHistories: (v: any) => void;
  setMyProfileData: (v: any) => void;
  reportData: any;
  setReportData: (v: any) => void;
  hint: any;
  setHint: (v: any) => void;
  currentHistoryId: number | null;
  setCurrentHistoryId: (v: any) => void;
  savedReport: any;
  setSavedReport: (v: any) => void;
  pendingResumeData: any;
  setPendingResumeData: (v: any) => void;
  // From useChat
  status: string;
  setStatus: (v: string) => void;
  aiText: string;
  history: string;
  sendMessage: (text: string, jd: string, voice: string, mode: string, cb: (blob: Blob) => void) => void;
  resetChat: () => void;
  interruptChat: () => void;
  loadSession: (rawHistory: string, lastMsg: string, chat: any[]) => void;
  // From useMicrophone
  userText: string;
  tempText: string;
  isListening: boolean;
  toggleMic: () => void;
  resetText: () => void;
  // From useAudioQueue
  playAudio: (blob: Blob) => void;
  stopAudio: () => void;
  // From useInterviewTimer
  timeLeft: number;
  questionCount: number;
  setQuestionCount: (v: number) => void;
  resetTimer: () => void;
  advanceQuestion: () => void;
}

export function useInterviewActions(params: UseInterviewActionsParams) {
  const {
    user,
    config,
    setConfig,
    hasStarted,
    setHasStarted,
    toggleModal,
    setIsAdmin,
    interviewHistories,
    setInterviewHistories,
    setMyProfileData,
    setReportData,
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
  } = params;

  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [hasNewMessages, setHasNewMessages] = useState(false);

  const handleInterrupt = () => {
    interruptChat();
    stopAudio();
    if (isListening) toggleMic();
    setStatus("Ready");
  };

  const handleNewChat = () => {
    handleInterrupt();
    resetChat();
    setReportData(null);
    setCurrentHistoryId(null);
    setSavedReport(null);
    setHasNewMessages(false);
    setHasStarted(false);
    resetTimer();
    toast.success("Started a new interview session!");
  };

  const handleSend = async (isTimeout: boolean | React.MouseEvent = false) => {
    const timeoutFlag = isTimeout === true;

    let input = (userText + " " + tempText).trim();

    if (timeoutFlag) {
      input =
        "[SYSTEM]: Time's up. Please move to the next question.";
      if (isListening) toggleMic();
    } else {
      if (!input && timeLeft > 0) return;
    }

    if (!user) {
      const guestCount = parseInt(
        localStorage.getItem("guest_msg_count") || "0",
      );
      if (guestCount >= 10) {
        toast.error(
          "You've used all free interactions. Please log in to continue!",
          {
            duration: 5000,
          },
        );
        return;
      }
      localStorage.setItem("guest_msg_count", (guestCount + 1).toString());
    }

    resetText();

    if (savedReport) {
      setSavedReport(null);
    }
    setHasNewMessages(true);
    if (config.interviewType === "timed") {
      if (questionCount >= config.questionLimit) {
        setStatus("Scoring...");
        sendMessage(
          input || "I have completed my answer.",
          config.jd,
          config.voice,
          config.mode,
          () => {},
        );
        handleOpenReport(true);
        return;
      }
      advanceQuestion();
    }

    sendMessage(
      input || "Sorry, I didn't have time to answer this one.",
      config.jd,
      config.voice,
      config.mode,
      (blob) => playAudio(blob),
    );
  };

  const handleOpenReport = async (isAutoFinish = false) => {
    if (isGeneratingReport) return;
    setIsGeneratingReport(true);

    if (!isAutoFinish) handleInterrupt();
    if (!user) {
      toast.error("Please log in to use this feature!", {
        duration: 5000,
        position: "top-center",
      });
      setStatus("Ready");
      setIsGeneratingReport(false);
      return;
    }
    toggleModal("report", true);

    if (savedReport && !hasNewMessages) {
      setReportData(savedReport);
      setStatus("Ready");
      setIsGeneratingReport(false);
      return;
    }

    const currentHistory = history.trim();
    if (!currentHistory) {
      setReportData(null);
      setIsGeneratingReport(false);
      return;
    }

    try {
      const d = await endInterview(
        currentHistory,
        config.jd,
        config.position,
        currentHistoryId || undefined,
        config.interviewType,
        config.questionLimit,
        config.timeLimit,
      );
      setReportData(d.report);
      if (d.history_id) setCurrentHistoryId(d.history_id);
      setStatus("Ready");
      if (user) {
        getHistory().then((data) =>
          setInterviewHistories(data.histories || []),
        );
      }
    } catch (error) {
      console.log("Scoring error", error);
      toast.error("Scoring failed! Please try again.");
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const handleRetry = () => {
    toggleModal("report", false);
    resetChat();
    setReportData(null);
    setCurrentHistoryId(null);
    setSavedReport(null);
    setHasNewMessages(false);
    stopAudio();
    setHasStarted(false);
    resetTimer();
  };

  const startTimedInterview = () => {
    setHasStarted(true);
    resetTimer();
    setQuestionCount(1);
    setStatus("Processing");

    const companyText = config.company ? `at ${config.company}` : "";
    const prompt = `I am applying for the position of ${config.position} ${companyText}. Requirements: ${config.jd}. Act as a professional HR interviewer, SKIP greetings, and immediately ask the FIRST QUESTION (deep-dive into a situation or skill) to interview me.`;

    sendMessage(prompt, config.jd, config.voice, config.mode, (blob) =>
      playAudio(blob),
    );
  };

  const onMicClick = () => {
    if (
      status === "Processing" ||
      status === "AI Speaking" ||
      status === "Scoring..."
    )
      handleInterrupt();
    else {
      toggleMic();
      if (!isListening) setStatus("Listening");
      else setStatus("Ready");
    }
  };

  const handleLoadOldInterview = (h: any) => {
    if (!h.details || h.details.length === 0) return;
    setCurrentHistoryId(h.id);
    setSavedReport({
      score: h.score,
      overall_feedback: h.overall_feedback,
      details: h.details || [],
      inferred_position: h.position || h.title || "Free",
      final_scores: h.final_scores,
      top_skills_to_improve: h.top_skills_to_improve,
      strong_topics: h.strong_topics,
      weak_topics: h.weak_topics,
    });
    setReportData({
      score: h.score,
      overall_feedback: h.overall_feedback,
      details: h.details || [],
      inferred_position: h.position || h.title || "Free",
      final_scores: h.final_scores,
      top_skills_to_improve: h.top_skills_to_improve,
      strong_topics: h.strong_topics,
      weak_topics: h.weak_topics,
    });
    toggleModal("report", true);
  };

  const handleConfirmResume = async (resumeSettings: any) => {
    const h = pendingResumeData;
    if (!h) return;
    setHasNewMessages(false);

    let rawHistory = "";
    let lastQuestion = "";
    let reconstructedChat: any[] = [];

    h.details.forEach((d: any) => {
      rawHistory += `\nAI: ${d.question}\nCandidate: ${d.candidate_answer}`;
      lastQuestion = d.question;

      reconstructedChat.push({ role: "assistant", content: d.question });
      if (
        d.candidate_answer &&
        d.candidate_answer !== "Candidate did not answer"
      ) {
        reconstructedChat.push({ role: "user", content: d.candidate_answer });
      }
    });

    setConfig({
      ...config,
      position: h.position || "Free",
      interviewType: resumeSettings.interviewType,
      questionLimit: resumeSettings.questionLimit,
      timeLimit: resumeSettings.timeLimit,
    });

    setHasStarted(true);
    setCurrentHistoryId(h.id);

    setSavedReport({
      score: h.score,
      overall_feedback: h.overall_feedback,
      details: h.details || [],
      inferred_position: h.position || "Free",
      final_scores: h.final_scores,
      top_skills_to_improve: h.top_skills_to_improve,
      strong_topics: h.strong_topics,
      weak_topics: h.weak_topics,
    });

    if (resumeSettings.interviewType === "timed") {
      resetTimer();
      setQuestionCount(h.details.length + 1);
    }

    try {
      await updateInterviewConfig(h.id, {
        interview_type: resumeSettings.interviewType,
        question_limit: resumeSettings.questionLimit,
        time_limit: resumeSettings.timeLimit,
      });
      setInterviewHistories(
        interviewHistories.map((item: any) =>
          item.id === h.id
            ? {
                ...item,
                interview_type: resumeSettings.interviewType,
                question_limit: resumeSettings.questionLimit,
                time_limit: resumeSettings.timeLimit,
              }
            : item,
        ),
      );
    } catch (err) {
      console.warn("Failed to update interview config:", err);
    }

    loadSession(
      rawHistory,
      "Welcome back. " + lastQuestion,
      reconstructedChat,
    );
    toggleModal("resumeConfig", false);
    setPendingResumeData(null);
    toast.success(
      `Restored interview session for: ${h.position || h.title}`,
    );
  };

  const handleHintClick = async () => {
    setHint({ show: true, content: "Thinking..." });
    try {
      const lang = config.voice?.startsWith("en-") ? "en" : "vi";
      const d = await getHint(aiText, config.jd, lang);
      setHint({ show: true, content: d.hint });
    } catch (error) {
      setHint({ show: true, content: "Could not get hint." });
      toast.error("Could not get hint at this time.");
    }
  };

  const loadInitialData = () => {
    if (user) {
      getMyProfile()
        .then((data) => {
          setMyProfileData(data);
        })
        .catch(() => {});

      getAdminDashboard()
        .then(() => setIsAdmin(true))
        .catch(() => setIsAdmin(false));

      getHistory()
        .then((data) => setInterviewHistories(data.histories || []))
        .catch(() => {});
    } else {
      setIsAdmin(false);
    }
  };

  return {
    isGeneratingReport,
    handleInterrupt,
    handleNewChat,
    handleSend,
    handleOpenReport,
    handleRetry,
    startTimedInterview,
    onMicClick,
    handleLoadOldInterview,
    handleConfirmResume,
    handleHintClick,
    loadInitialData,
  };
}
