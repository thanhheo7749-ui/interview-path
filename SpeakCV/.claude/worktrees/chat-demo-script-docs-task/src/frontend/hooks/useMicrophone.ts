/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useState, useRef, useCallback, useEffect } from "react";

export const useMicrophone = (lang: string = "en-US") => {
  const [text, setText] = useState("");
  const [temp, setTemp] = useState(""); 
  const [isListening, setIsListening] = useState(false);
  
  const recognitionRef = useRef<any>(null); 
  const shouldRestartRef = useRef(false);

  // Initialize the browser's speech recognition instance
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = lang;
        recognition.maxAlternatives = 3; // Consider more alternatives for better accuracy

        recognition.onresult = (event: any) => {
          let finalTxt = "";
          let interimTxt = "";

          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              // Pick the highest-confidence alternative
              finalTxt += event.results[i][0].transcript;
            } else {
              interimTxt += event.results[i][0].transcript;
            }
          }

          // Finalized sentence -> append to main chat text
          if (finalTxt) {
            setText((prev) => (prev + " " + finalTxt).trim());
          }
          // Interim text (still speaking) -> show as draft
          setTemp(interimTxt); 
        };

        recognition.onend = () => {
          // Auto-restart if the user hasn't explicitly stopped
          // (Chrome cuts off recognition after ~60s of silence or pauses)
          if (shouldRestartRef.current) {
            try {
              recognition.start();
              return; // Don't set isListening to false
            } catch (e) {
              // If restart fails, fall through to cleanup
            }
          }
          
          setIsListening(false);
          // Flush remaining interim text into the main chat
          setTemp((prevTemp) => {
            if (prevTemp) {
              setText((prevText) => (prevText + " " + prevTemp).trim());
            }
            return "";
          });
        };

        recognition.onerror = (event: any) => {
          // "no-speech" is common and not a real error - just keep going
          if (event.error === "no-speech") return;
          console.error("Mic error:", event.error);
          shouldRestartRef.current = false;
          setIsListening(false);
        };

        recognitionRef.current = recognition;
      }
    }
  }, [lang]);

  const startRecording = () => {
    if (recognitionRef.current) {
      try {
        shouldRestartRef.current = true;
        recognitionRef.current.start();
        setIsListening(true);
        setTemp("");
      } catch (e) {
        console.log("Mic is already active");
      }
    } else {
      alert("Your browser does not support this feature (please use Chrome or Edge).");
    }
  };

  const stopRecording = () => {
    shouldRestartRef.current = false;
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  };

  const toggleMic = useCallback(() => {
    if (isListening) stopRecording(); else startRecording();
  }, [isListening]);

  const resetText = () => { setText(""); setTemp(""); };

  return { text, setText, temp, isListening, isProcessing: false, toggleMic, resetText };
};