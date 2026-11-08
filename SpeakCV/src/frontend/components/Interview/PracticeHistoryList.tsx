/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useState } from "react";
import { PlusCircle, MoreVertical, Edit2, Trash2 } from "lucide-react";
import { renameInterview, deleteInterview } from "@/services/api";
import toast from "react-hot-toast";

interface PracticeHistoryListProps {
  user: any;
  interviewHistories: any[];
  setInterviewHistories: (val: any) => void;
  currentHistoryId?: number | null;
  handleLoadOldInterview: (h: any) => void;
  handleRetry: () => void;
}

const LockIcon = ({ size, className }: any) => (
  <svg
    className={className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
  </svg>
);

export function PracticeHistoryList({
  user,
  interviewHistories,
  setInterviewHistories,
  currentHistoryId,
  handleLoadOldInterview,
  handleRetry,
}: PracticeHistoryListProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  const handleRename = async (id: number) => {
    if (!editTitle.trim()) return;
    const previousHistories = [...interviewHistories];
    const newHistories = interviewHistories.map((h) =>
      h.id === id
        ? { ...h, title: editTitle, position: editTitle.replace("Interview ", "") }
        : h,
    );
    setInterviewHistories(newHistories);
    setEditingId(null);
    toast.success("Renamed successfully!");

    try {
      await renameInterview(id, editTitle);
    } catch {
      setInterviewHistories(previousHistories);
      toast.error("Rename failed! Reverted.");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this history?")) return;
    const previousHistories = [...interviewHistories];
    const newHistories = interviewHistories.filter((h) => h.id !== id);
    setInterviewHistories(newHistories);
    toast.success("Deleted successfully!");
    if (currentHistoryId === id) {
      handleRetry();
    }

    try {
      await deleteInterview(id);
    } catch {
      setInterviewHistories(previousHistories);
      toast.error("Delete failed! Reverted.");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar relative">
      <div className="flex justify-between items-center sticky top-0 bg-theme-primary px-4 pt-4 pb-3 z-10 border-b border-theme-border/50">
        <h3 className="text-xs font-black text-theme-muted uppercase tracking-widest">
          Practice History
        </h3>
        <button
          onClick={handleRetry}
          className="text-blue-400 hover:text-theme-text p-1.5 bg-blue-500/10 rounded-lg hover:bg-blue-700/20 transition-colors"
          title="Start new interview"
        >
          <PlusCircle size={16} />
        </button>
      </div>

      {user ? (
        interviewHistories.length > 0 ? (
          <div className="space-y-1 px-4 pt-3 pb-10">
            {(() => {
              const groups: { label: string; items: any[] }[] = [];
              const now = new Date();
              const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
              const yesterday = new Date(today.getTime() - 86400000);
              const weekAgo = new Date(today.getTime() - 7 * 86400000);

              const todayItems: any[] = [];
              const yesterdayItems: any[] = [];
              const weekItems: any[] = [];
              const olderItems: any[] = [];

              interviewHistories.forEach((h: any) => {
                const d = new Date(h.created_at);
                if (d >= today) todayItems.push(h);
                else if (d >= yesterday) yesterdayItems.push(h);
                else if (d >= weekAgo) weekItems.push(h);
                else olderItems.push(h);
              });

              if (todayItems.length) groups.push({ label: "Today", items: todayItems });
              if (yesterdayItems.length) groups.push({ label: "Yesterday", items: yesterdayItems });
              if (weekItems.length) groups.push({ label: "Last Week", items: weekItems });
              if (olderItems.length) groups.push({ label: "Older", items: olderItems });

              return groups.map((group) => (
                <div key={group.label} className="mb-3">
                  <p className="text-[10px] font-black text-theme-muted uppercase tracking-widest px-1 py-2">
                    {group.label}
                  </p>
                  <div className="space-y-2">
                    {group.items.map((h: any, i: number) => (
                      <div
                        key={h.id || i}
                        onClick={() => handleLoadOldInterview(h)}
                        className={`p-3 bg-theme-primary border rounded-xl transition-all group relative cursor-pointer ${
                          currentHistoryId === h.id
                            ? "border-blue-500 bg-theme-surface/80 ring-1 ring-blue-500/30"
                            : "border-theme-border/40 hover:border-blue-500/50 hover:bg-theme-surface/50"
                        }`}
                      >
                        {/* Top row: Title + Score + Menu */}
                        <div className="flex items-start gap-2">
                          {editingId === h.id ? (
                            <input
                              autoFocus
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              onBlur={() => handleRename(h.id)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleRename(h.id);
                                if (e.key === "Escape") setEditingId(null);
                              }}
                              className="flex-1 bg-theme-secondary text-theme-text text-sm px-2 py-1 rounded outline-none border border-blue-500 cursor-text"
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <span
                              className="font-bold text-sm truncate flex-1 text-theme-text group-hover:text-blue-400 transition-colors leading-snug"
                              title={h.title || h.position}
                            >
                              {h.title || h.position || "New Interview"}
                            </span>
                          )}

                          <div className="flex items-center gap-1 shrink-0">
                            <span
                              className={`text-[11px] font-black px-1.5 py-0.5 rounded-md leading-none ${
                                h.score >= 8
                                  ? "bg-emerald-500/20 text-emerald-400"
                                  : h.score >= 5
                                    ? "bg-yellow-500/20 text-yellow-400"
                                    : "bg-red-500/20 text-red-400"
                              }`}
                            >
                              {h.score}
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenMenuId(openMenuId === h.id ? null : h.id);
                              }}
                              className="text-theme-muted hover:text-theme-text p-0.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <MoreVertical size={14} />
                            </button>
                          </div>
                        </div>

                        {/* Bottom row: Mode badge + Date + Action */}
                        <div className="flex items-center justify-between mt-2">
                          <div className="flex items-center gap-1.5 text-[10px] text-theme-text-secondary">
                            <span
                              className={`font-bold px-1.5 py-0.5 rounded text-[10px] truncate max-w-[90px] transition-all duration-300 ${
                                h.interview_type === "timed"
                                  ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                                  : "bg-theme-surface/80 text-theme-text-secondary border border-theme-border/50"
                              }`}
                            >
                              {h.interview_type === "timed" ? "⚡ Stress" : "Free"}
                            </span>
                            <span className="text-theme-muted">•</span>
                            <span>{new Date(h.created_at).toLocaleDateString("en-US")}</span>
                          </div>

                          <span
                            className={`text-[10px] uppercase font-bold transition-opacity ${
                              currentHistoryId === h.id
                                ? "text-emerald-400 opacity-100"
                                : "text-blue-400 opacity-0 group-hover:opacity-100"
                            }`}
                          >
                            {currentHistoryId === h.id ? "Active ●" : "View report →"}
                          </span>
                        </div>

                        {/* Context menu */}
                        {openMenuId === h.id && (
                          <div
                            className="absolute right-2 top-10 bg-theme-surface border border-theme-border rounded-lg shadow-xl z-50 py-1 w-32"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={() => {
                                setEditTitle(h.title || h.position || "Free Interview");
                                setEditingId(h.id);
                                setOpenMenuId(null);
                              }}
                              className="w-full text-left px-3 py-1.5 text-xs text-theme-text hover:bg-theme-border flex items-center gap-2"
                            >
                              <Edit2 size={12} /> Rename
                            </button>
                            <button
                              onClick={() => {
                                handleDelete(h.id);
                                setOpenMenuId(null);
                              }}
                              className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-theme-border flex items-center gap-2"
                            >
                              <Trash2 size={12} /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ));
            })()}
          </div>
        ) : (
          <div className="text-center text-theme-muted text-sm mt-10 italic">
            No history yet.
            <br />
            Start your first interview!
          </div>
        )
      ) : (
        <div className="text-center text-slate-600 text-sm mt-10">
          <LockIcon className="mx-auto mb-2 opacity-50" size={24} />
          Log in to save your history
        </div>
      )}
    </div>
  );
}
