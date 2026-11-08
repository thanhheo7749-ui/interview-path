/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useRouter } from "next/navigation";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { PracticeStepper, type PracticeStep } from "@/components/Interview/steps/PracticeStepper";

interface PracticeTopBarProps {
  step: PracticeStep;
  right?: React.ReactNode;
}

export function PracticeTopBar({ step, right }: PracticeTopBarProps) {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 flex items-center justify-between gap-4 px-4 py-3 bg-theme-secondary/90 backdrop-blur-md border-b border-theme-border">
      <h1
        className="text-xl font-black italic bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent cursor-pointer shrink-0"
        onClick={() => router.push("/")}
      >
        SpeakCV
      </h1>

      <div className="hidden sm:flex">
        <PracticeStepper step={step} />
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {right}
        <button
          onClick={toggleTheme}
          className="p-2.5 bg-theme-surface/80 border border-theme-border rounded-xl text-theme-text-secondary hover:text-yellow-400 backdrop-blur-sm shadow-lg transition-all hover:scale-105"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </div>

      <div className="sm:hidden w-full order-3">
        <PracticeStepper step={step} />
      </div>
    </header>
  );
}
