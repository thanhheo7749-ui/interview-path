/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useState } from "react";
import { Settings, Flag, ChevronLeft, ChevronUp, ChevronDown, Briefcase } from "lucide-react";

import { UserMenu } from "@/components/Interview/UserMenu";
import { PrepareMenuItems } from "@/components/Interview/PrepareMenuItems";
import { PracticeHistoryList } from "@/components/Interview/PracticeHistoryList";

interface SidebarProps {
  user: any;
  myProfileData: any;
  isAdmin: boolean;
  interviewHistories: any[];
  logout: () => void;
  toggleModal: (key: string, val: boolean) => void;
  handleLoadOldInterview: (h: any) => void;
  handleRetry: () => void;
  handleOpenReport: (isAutoFinish?: boolean) => void;
  setInterviewHistories: (val: any) => void;
  currentHistoryId?: number | null;
  handleNewChat: () => void;
  isGeneratingReport?: boolean;
  onOpenSubscription?: () => void;
  isOpen?: boolean;
  onClose?: () => void;
  onOpenCameraMode?: () => void;
}

export function Sidebar({
  user,
  myProfileData,
  isAdmin,
  interviewHistories,
  logout,
  toggleModal,
  handleLoadOldInterview,
  handleRetry,
  handleOpenReport,
  setInterviewHistories,
  currentHistoryId,
  isGeneratingReport,
  onOpenSubscription,
  isOpen = false,
  onClose,
  onOpenCameraMode,
}: SidebarProps) {
  const [showToolsMenu, setShowToolsMenu] = useState(false);

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-900/45 z-30 md:hidden backdrop-blur-sm"
          onClick={onClose}
        />
      )}
      <nav
        className={`w-72 bg-theme-primary border-r border-theme-border flex flex-col z-40 shadow-2xl transition-transform duration-300 absolute inset-y-0 left-0 md:relative md:translate-x-0 ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        {/* Close Button on Mobile */}
        <div
          className={`md:hidden absolute top-1/2 -right-4 -translate-y-1/2 z-50 transition-opacity duration-300 ${isOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        >
          <button
            onClick={onClose}
            className="p-1.5 bg-theme-surface border-y border-r border-l-0 border-theme-border rounded-r-xl text-theme-text-secondary hover:text-theme-text transition-colors shadow-lg"
          >
            <ChevronLeft size={20} />
          </button>
        </div>

        {/* 1. AVATAR & USER MENU SECTION */}
        <div className="p-4 border-b border-theme-border relative z-50">
          <UserMenu
            user={user}
            myProfileData={myProfileData}
            isAdmin={isAdmin}
            logout={logout}
            onOpenSubscription={onOpenSubscription}
          />
        </div>

        {/* 2. TOOLS COMBO BOX */}
        <div className="p-4 border-b border-theme-border">
          <button
            onClick={() => setShowToolsMenu(!showToolsMenu)}
            className="w-full flex items-center justify-between p-3 bg-theme-primary border border-theme-border hover:border-theme-text-secondary rounded-xl text-theme-text font-bold transition-colors"
          >
            <span className="flex items-center gap-2 text-sm">
              <Briefcase size={18} className="text-yellow-500" /> Tools
            </span>
            {showToolsMenu ? (
              <ChevronUp size={16} className="text-theme-muted" />
            ) : (
              <ChevronDown size={16} className="text-theme-muted" />
            )}
          </button>

          {showToolsMenu && (
            <div className="mt-2 space-y-1 bg-theme-primary/50 p-2 border border-theme-border rounded-xl animate-in fade-in">
              <PrepareMenuItems
                user={user}
                toggleModal={toggleModal}
                onOpenCameraMode={onOpenCameraMode}
                onCloseMenu={() => setShowToolsMenu(false)}
              />
            </div>
          )}
        </div>

        {/* 3. INTERVIEW HISTORY SECTION */}
        <PracticeHistoryList
          user={user}
          interviewHistories={interviewHistories}
          setInterviewHistories={setInterviewHistories}
          currentHistoryId={currentHistoryId}
          handleLoadOldInterview={handleLoadOldInterview}
          handleRetry={handleRetry}
        />

        {/* 4. SETTINGS & END SESSION (Bottom) */}
        <div className="p-4 border-t border-theme-border flex gap-2 bg-theme-primary/90 backdrop-blur-md">
          <button
            onClick={() => toggleModal("settings", true)}
            className="flex-1 flex items-center justify-center gap-2 p-3 bg-theme-surface hover:bg-theme-border text-theme-text-secondary hover:text-theme-text rounded-xl transition-colors font-bold text-sm"
            aria-label="Settings"
          >
            <Settings size={18} /> Settings
          </button>

          <button
            onClick={() => handleOpenReport(false)}
            disabled={isGeneratingReport}
            className={`w-12 flex flex-shrink-0 items-center justify-center p-3 rounded-xl transition-all ${isGeneratingReport ? "bg-theme-surface text-theme-muted cursor-not-allowed" : "bg-red-50 hover:bg-red-100 text-red-600 hover:text-red-700"}`}
            title="Finish & Score"
            aria-label="Finish and score"
          >
            {isGeneratingReport ? (
              <div className="w-5 h-5 border-2 border-theme-border border-t-blue-600 rounded-full animate-spin" />
            ) : (
              <Flag size={18} />
            )}
          </button>
        </div>
      </nav>
    </>
  );
}
