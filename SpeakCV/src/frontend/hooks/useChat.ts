/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useState, useRef } from "react";
import { chatWithAI } from "@/services/api";
import toast from "react-hot-toast";

export type InterviewAnalysis = {
  transcript?: {
    transcript_confidence: number;
    low_quality_flag: boolean;
    word_count?: number;
    quality_reason?: string;
  };
  speaking_signals?: {
    filler_rate: number;
    clarity_score: number;
    speaking_signal: string;
    pause_hint?: number | null;
  };
  turn_evaluation?: {
    correctness: number;
    depth: number;
    communication: number;
    topic_relevance?: number;
  };
  interview_context?: {
    target_topics?: string[];
    highlighted_strengths?: string[];
    skill_gaps?: string[];
    match_score?: number;
    priority_topics?: string[];
    question_plan_seed?: Record<string, unknown>;
  };
  planner_decision?: {
    why_selected?: string;
    topic_state?: string;
    next_topic?: string;
    followup_mode?: string;
    question_strategy?: string;
  };
  live_cues?: string[];
  why_selected?: string;
  topic_state?: string;
  next_topic?: string;
  trace_id?: string;
  [key: string]: unknown;
};

export type InterviewUsage = {
  provider?: string;
  model?: string;
  latency_ms?: number;
  [key: string]: unknown;
};

const parseHeaderJson = <T,>(value: string | null): T | null => {
  if (!value) return null;
  try {
    return JSON.parse(decodeURIComponent(value)) as T;
  } catch {
    return null;
  }
};

const loadInterviewContext = (): Record<string, unknown> | null => {
  const raw = sessionStorage.getItem("interview_context");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
};

const storeInterviewContext = (context: Record<string, unknown> | null) => {
  if (!context) {
    sessionStorage.removeItem("interview_context");
    return;
  }
  sessionStorage.setItem("interview_context", JSON.stringify(context));
};

const parseInterviewHeaders = (res: Response) => ({
  responseText: decodeURIComponent(res.headers.get("X-AI-Response-Text") || ""),
  traceId: decodeURIComponent(res.headers.get("X-Interview-Trace-Id") || ""),
  analysis: parseHeaderJson<InterviewAnalysis>(res.headers.get("X-Interview-Analysis")),
  usage: parseHeaderJson<InterviewUsage>(res.headers.get("X-Interview-Usage")),
});

const readInterviewContextPayload = () => loadInterviewContext();
const maybeStoreInterviewContext = (analysis: InterviewAnalysis | null) => {
  if (analysis?.interview_context) {
    storeInterviewContext(analysis.interview_context as Record<string, unknown>);
  }
};

export const useChat = () => {
  const [status, setStatus] = useState("Ready");
  const [aiText, setAiText] = useState("Hello, I'm your AI Interviewer. Are you ready?");
  const [history, setHistory] = useState("");
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [analysis, setAnalysis] = useState<InterviewAnalysis | null>(null);
  const [usage, setUsage] = useState<InterviewUsage | null>(null);
  const [traceId, setTraceId] = useState("");
  const abortCtrl = useRef<AbortController | null>(null);

  const sendMessage = async (
    userText: string, 
    jd: string, 
    voice: string, 
    mode: string,
    onAudioReceived: (blob: Blob) => void 
  ) => {
    if (!userText.trim()) return;

    setStatus("Processing");
    setHistory(prev => prev + `\nCandidate: ${userText}`);
    
    const currentChatHistory = [...chatHistory];
    setChatHistory(prev => [...prev, { role: "user", content: userText }]);

    if (abortCtrl.current) abortCtrl.current.abort();
    abortCtrl.current = new AbortController();

    try {
      const lang = voice?.toLowerCase().startsWith("en-") ? "en" : "vi";
      const res = await chatWithAI(
        userText,
        jd,
        voice,
        mode,
        currentChatHistory,
        abortCtrl.current.signal,
        lang,
        readInterviewContextPayload(),
      );

      const parsed = parseInterviewHeaders(res);
      if (parsed.analysis) {
        setAnalysis(parsed.analysis);
        maybeStoreInterviewContext(parsed.analysis);
      }
      if (parsed.usage) {
        setUsage(parsed.usage);
      }
      if (parsed.traceId) {
        setTraceId(parsed.traceId);
      }
      
      if (res.status === 429) {
        toast.error("You've used all free interactions. Please log in to continue!", {
          duration: 5000,
          position: "top-center"
        });
        setStatus("Ready");
        return;
      }

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      if (parsed.responseText) {
        setAiText(parsed.responseText);
        setHistory(prev => prev + `\nAI: ${parsed.responseText}`);
        setChatHistory(prev => [...prev, { role: "assistant", content: parsed.responseText }]);
      }

      const blob = await res.blob();
      if (blob.size > 0) {
        setStatus("AI Speaking");
        onAudioReceived(blob); 
      } else {
        setStatus("Ready");
      }

      // Automatically refresh tokens on successful AI reply
      window.dispatchEvent(new Event("auth-changed"));

    } catch (e: any) {
      if (e.name !== 'AbortError') {
        toast.error("Connection error or server overloaded!");
        setStatus("Ready");
      }
    }
  };

  const resetChat = () => {
    setHistory("");
    setChatHistory([]);
    setAiText("Let's start over. Please introduce yourself!");
    setStatus("Ready");
    if (abortCtrl.current) abortCtrl.current.abort();
  };

  const interrupt = () => {
      if (abortCtrl.current) abortCtrl.current.abort();
      setStatus("Ready");
  };

  const loadSession = (historyStr: string, lastQuestion: string, initialChatHistory: any[] = []) => {
    setHistory(historyStr);
    setChatHistory(initialChatHistory);
    setAiText(lastQuestion);
    setStatus("Ready");
  };

  return {
    status,
    setStatus,
    aiText,
    setAiText,
    history,
    chatHistory,
    setChatHistory,
    analysis,
    usage,
    traceId,
    sendMessage,
    resetChat,
    interrupt,
    loadSession,
  };
};
