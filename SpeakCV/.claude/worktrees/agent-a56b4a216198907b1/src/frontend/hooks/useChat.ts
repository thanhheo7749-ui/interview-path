/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useState, useRef } from "react";
import { chatWithAI } from "@/services/api"; 
import toast from "react-hot-toast";

export const useChat = () => {
  const [status, setStatus] = useState("Ready");
  const [aiText, setAiText] = useState("Hello, I'm your AI Interviewer. Are you ready?");
  const [history, setHistory] = useState("");
  const [chatHistory, setChatHistory] = useState<any[]>([]);
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
      const res = await chatWithAI(userText, jd, voice, mode, currentChatHistory, abortCtrl.current.signal, lang);
      
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

      const responseText = decodeURIComponent(res.headers.get("X-AI-Response-Text") || "");
      if (responseText) {
        setAiText(responseText);
        setHistory(prev => prev + `\nAI: ${responseText}`);
        setChatHistory(prev => [...prev, { role: "assistant", content: responseText }]);
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
    status, setStatus, aiText, setAiText, history, chatHistory, setChatHistory, sendMessage, resetChat, interrupt, loadSession
  };
};
