import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { WebcamView } from "./WebcamView";
import { AvatarHR } from "./AvatarHR";
import { useAudioAnalyser } from "@/hooks/useAudioAnalyser";

interface InlineCameraWidgetProps {
  onClose: () => void;
  audioElement?: HTMLAudioElement | null;
  isPlayingAudio: boolean;
  isStressMode?: boolean;
}

export function InlineCameraWidget({
  onClose,
  audioElement,
  isPlayingAudio,
  isStressMode = false,
}: InlineCameraWidgetProps) {
  const [isMobile, setIsMobile] = useState(false);
  
  // Use the audio analyser hook to get real-time amplitude
  const amplitude = useAudioAnalyser(audioElement, isPlayingAudio);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className="relative w-full max-w-4xl mx-auto h-[250px] md:h-[300px] bg-slate-900 rounded-3xl overflow-hidden shadow-2xl border border-white/10 flex md:flex-row flex-col animate-in slide-in-from-top-10 fade-in duration-300 mb-2">
      {/* Close Button (hidden in Stress Mode) */}
      {!isStressMode && (
        <button 
          onClick={onClose}
          className="absolute top-3 right-3 z-50 w-8 h-8 rounded-full bg-black/40 hover:bg-black/60 flex items-center justify-center text-white backdrop-blur-md transition-colors"
          aria-label="Close Camera"
        >
          <X size={16} />
        </button>
      )}

      {/* Main Content Area */}
      {isMobile ? (
        // Mobile Layout: Avatar full, User PiP
        <>
          <div className="absolute inset-0">
            <AvatarHR 
              className="w-full h-full" 
              audioAmplitude={amplitude}
            />
          </div>
          <div className="absolute bottom-4 right-4 w-24 h-32 z-40 rounded-xl overflow-hidden shadow-2xl border-2 border-white/20">
            <WebcamView className="w-full h-full" />
          </div>
        </>
      ) : (
        // Desktop Layout: Side-by-side
        <>
          <div className="flex-1 border-r border-white/10 bg-black/50">
            <WebcamView className="w-full h-full" />
          </div>
          <div className="flex-1 bg-gradient-to-b from-slate-800 to-slate-900 relative">
            <AvatarHR 
              className="w-full h-full" 
              audioAmplitude={amplitude}
            />
          </div>
        </>
      )}
    </div>
  );
}
