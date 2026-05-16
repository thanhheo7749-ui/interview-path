/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useEffect, useState } from "react";

interface AvatarHRProps {
  className?: string;
  audioAmplitude?: number; // 0.0 to 1.0, representing mouth openness
}

export function AvatarHR({ className = "", audioAmplitude = 0 }: AvatarHRProps) {
  const [isBlinking, setIsBlinking] = useState(false);

  // Random blink animation loop
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const scheduleBlink = () => {
      // Random interval between 2s and 6s
      const nextBlink = Math.random() * 4000 + 2000;
      
      timeoutId = setTimeout(() => {
        setIsBlinking(true);
        // Keep eyes closed for 150ms
        setTimeout(() => setIsBlinking(false), 150);
        
        // Schedule next blink
        scheduleBlink();
      }, nextBlink);
    };

    scheduleBlink();

    return () => clearTimeout(timeoutId);
  }, []);

  // Map audio amplitude to jaw offset (0 to 15px downward)
  // Multiply by 2.5 for responsiveness, cap at 15px to stay within face bounds
  const jawOffset = Math.min(15, audioAmplitude * 2.5 * 15);
  
  // A subtle breathing effect based on time
  const [breathingScale, setBreathingScale] = useState(1);
  useEffect(() => {
    let animationFrameId: number;
    let startTime = Date.now();

    const animateBreathing = () => {
      const elapsed = Date.now() - startTime;
      // Sine wave for smooth breathing oscillation (3 second cycle)
      // Base scale 1.0, varies between 0.99 and 1.01
      const scale = 1.0 + Math.sin(elapsed / 1500 * Math.PI) * 0.01;
      setBreathingScale(scale);
      animationFrameId = requestAnimationFrame(animateBreathing);
    };

    animateBreathing();
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  return (
    <div className={`relative bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden ${className}`}>
      {/* Background pattern for depth */}
      <div className="absolute inset-0 opacity-[0.03] dark:opacity-10" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, currentColor 1px, transparent 0)', backgroundSize: '24px 24px' }}></div>
      
      {/* Avatar Container with breathing animation */}
      <div 
        className="h-[120%] max-h-[400px] aspect-square relative z-10 transition-transform duration-75 ease-in-out"
        style={{ transform: `scale(${breathingScale}) translateY(${(1 - breathingScale) * 100}px)` }}
      >
        <svg viewBox="0 0 400 400" className="w-full h-full drop-shadow-2xl">
          {/* Base Head/Face */}
          <rect x="160" y="250" width="80" height="80" rx="20" fill="#fcdbb3" /> {/* Neck */}
          <path d="M120 180 Q120 300 200 300 Q280 300 280 180 Q280 80 200 80 Q120 80 120 180 Z" fill="#ffe0bd" /> {/* Face Base */}
          
          {/* Ears */}
          <circle cx="120" cy="190" r="15" fill="#fcdbb3" />
          <circle cx="280" cy="190" r="15" fill="#fcdbb3" />

          {/* Hair (Professional bob cut) */}
          <path d="M110 160 Q100 80 200 60 Q300 80 290 160 L290 220 Q300 240 285 240 L270 200 Q270 100 200 90 Q130 100 130 200 L115 240 Q100 240 110 220 Z" fill="#2d3748" />

          {/* Eyebrows */}
          <path d="M140 150 Q160 140 180 150" fill="none" stroke="#2d3748" strokeWidth="6" strokeLinecap="round" />
          <path d="M220 150 Q240 140 260 150" fill="none" stroke="#2d3748" strokeWidth="6" strokeLinecap="round" />

          {/* Eyes (Grouped for blinking) */}
          <g style={{ transformOrigin: '200px 175px', transform: isBlinking ? 'scaleY(0.1)' : 'scaleY(1)', transition: 'transform 0.05s ease' }}>
            <circle cx="160" cy="175" r="8" fill="#1a202c" />
            <circle cx="240" cy="175" r="8" fill="#1a202c" />
            {/* Eye highlights */}
            <circle cx="163" cy="172" r="3" fill="white" />
            <circle cx="243" cy="172" r="3" fill="white" />
          </g>

          {/* Nose */}
          <path d="M200 185 Q205 205 195 210" fill="none" stroke="#e2b88a" strokeWidth="4" strokeLinecap="round" />

          {/* Mouth (Animated via audioAmplitude using dynamic SVG coordinates) */}
          
          {/* Dark mouth interior - stretches from top lip down to bottom lip */}
          <path 
            d={`M170 245 L230 245 Q200 ${260 + jawOffset} 170 245 Z`} 
            fill="#742a2a" 
            style={{ transition: 'd 0.05s linear' }}
          />

          {/* Top lip (static) */}
          <path d="M165 245 Q200 235 235 245" fill="none" stroke="#c53030" strokeWidth="5" strokeLinecap="round" />

          {/* Teeth hint (just below top lip, visible when mouth opens) */}
          {jawOffset > 3 && (
            <path d="M175 249 Q200 253 225 249" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" />
          )}

          {/* Bottom lip (dynamic y position) */}
          <path 
            d={`M170 ${245 + jawOffset} Q200 ${258 + jawOffset} 230 ${245 + jawOffset}`} 
            fill="none" stroke="#c53030" strokeWidth="4" strokeLinecap="round"
            style={{ transition: 'd 0.05s linear' }}
          />

          {/* Body/Suit */}
          <path d="M130 300 L90 400 L310 400 L270 300 Z" fill="#1e293b" /> {/* Jacket */}
          <path d="M160 300 L200 350 L240 300 Z" fill="#f8fafc" /> {/* Shirt */}
          {/* Tie */}
          <path d="M195 320 L205 320 L210 380 L200 390 L190 380 Z" fill="#0284c7" />
        </svg>
      </div>

      {/* Name Tag Overlay */}
      <div className="absolute bottom-4 left-4 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg text-slate-800 dark:text-white text-xs font-bold border border-slate-200 dark:border-slate-700 shadow-lg z-10 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-blue-500"></span>
        AI HR Specialist
      </div>
    </div>
  );
}
