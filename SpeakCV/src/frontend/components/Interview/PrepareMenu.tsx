/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useState } from "react";
import { Briefcase, ChevronDown, ChevronUp } from "lucide-react";
import { PrepareMenuItems } from "@/components/Interview/PrepareMenuItems";

interface PrepareMenuProps {
  user: any;
  toggleModal: (key: string, val: boolean) => void;
  onOpenCameraMode?: () => void;
}

export function PrepareMenu({ user, toggleModal, onOpenCameraMode }: PrepareMenuProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-theme-border text-sm font-semibold text-theme-text-secondary hover:text-theme-text hover:bg-theme-surface"
      >
        <Briefcase size={16} className="text-yellow-500" /> Prepare
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {open && (
        <div className="absolute right-0 top-[110%] w-64 bg-theme-surface border border-theme-border rounded-xl shadow-2xl p-2 animate-in slide-in-from-top-2 z-50">
          <PrepareMenuItems
            user={user}
            toggleModal={toggleModal}
            onOpenCameraMode={onOpenCameraMode}
            onCloseMenu={() => setOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
