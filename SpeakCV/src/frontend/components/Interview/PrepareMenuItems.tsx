/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useRouter } from "next/navigation";
import { Sparkles, FileText, Wand2, BarChart3, HelpCircle, Camera } from "lucide-react";

interface PrepareMenuItemsProps {
  user: any;
  toggleModal: (key: string, val: boolean) => void;
  onOpenCameraMode?: () => void;
  onCloseMenu?: () => void;
}

export function PrepareMenuItems({ user, toggleModal, onOpenCameraMode, onCloseMenu }: PrepareMenuItemsProps) {
  const router = useRouter();

  return (
    <>
      <button
        onClick={() => toggleModal("cv", true)}
        className="w-full text-left px-3 py-2.5 text-sm text-theme-text-secondary hover:bg-theme-surface hover:text-yellow-400 rounded-lg flex items-center gap-3"
      >
        <Sparkles size={16} /> Create CV
      </button>
      <button
        id="tour-step-cv"
        onClick={() => toggleModal("review", true)}
        className="w-full text-left px-3 py-2.5 text-sm text-theme-text-secondary hover:bg-theme-surface hover:text-purple-400 rounded-lg flex items-center gap-3"
      >
        <FileText size={16} /> Review CV
      </button>
      <button
        onClick={() => toggleModal("makeover", true)}
        className="w-full text-left px-3 py-2.5 text-sm text-theme-text-secondary hover:bg-theme-surface hover:text-pink-400 rounded-lg flex items-center gap-3"
      >
        <Wand2 size={16} /> Edit CV
      </button>
      {user && (
        <>
          <div className="border-t border-theme-border/50 my-1" />
          <button
            onClick={() => router.push("/dashboard")}
            className="w-full text-left px-3 py-2.5 text-sm text-theme-text-secondary hover:bg-theme-surface hover:text-blue-400 rounded-lg flex items-center gap-3"
          >
            <BarChart3 size={16} /> My Dashboard
          </button>
          <button
            onClick={() => router.push("/questions")}
            className="w-full text-left px-3 py-2.5 text-sm text-theme-text-secondary hover:bg-theme-surface hover:text-emerald-400 rounded-lg flex items-center gap-3"
          >
            <HelpCircle size={16} /> Question Bank
          </button>
          {onOpenCameraMode && (
            <>
              <div className="border-t border-theme-border/50 my-1" />
              <button
                onClick={() => {
                  onOpenCameraMode();
                  if (onCloseMenu) onCloseMenu();
                }}
                className="w-full text-left px-3 py-2.5 text-sm text-theme-text-secondary hover:bg-theme-surface hover:text-indigo-400 rounded-lg flex items-center gap-3"
              >
                <Camera size={16} /> Camera Interview{" "}
                <span className="ml-auto text-[10px] bg-indigo-500/20 text-indigo-400 px-1.5 rounded">NEW</span>
              </button>
            </>
          )}
        </>
      )}
    </>
  );
}
