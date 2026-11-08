/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { Camera } from "lucide-react";
import { SetupForm } from "@/components/Interview/SetupForm";

interface SetupStepProps {
  config: any;
  setConfig: (c: any) => void;
  onStart: () => void;
  masterCvAvailable: boolean;
  masterCvStatus: string;
  cameraMode: boolean;
  setCameraMode: (v: boolean) => void;
  aside?: React.ReactNode;
  prefillNotice?: { label: string } | null;
  onClearPrefill?: () => void;
}

export function SetupStep({
  config,
  setConfig,
  onStart,
  masterCvAvailable,
  masterCvStatus,
  cameraMode,
  setCameraMode,
  aside,
  prefillNotice,
  onClearPrefill,
}: SetupStepProps) {
  return (
    <div className="w-full max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-6 items-start py-6 px-4">
      <SetupForm
        config={config}
        setConfig={setConfig}
        onStart={onStart}
        masterCvAvailable={masterCvAvailable}
        masterCvStatus={masterCvStatus}
        prefillNotice={prefillNotice}
        onClearPrefill={onClearPrefill}
      >
        <details className="rounded-xl border border-theme-border bg-theme-secondary/60 px-4 py-3 group">
          <summary className="text-xs font-bold text-slate-400 uppercase cursor-pointer select-none">
            Advanced options
          </summary>
          <label className="mt-3 flex items-center gap-2 text-sm text-theme-text-secondary">
            <input
              type="checkbox"
              checked={cameraMode}
              onChange={(e) => setCameraMode(e.target.checked)}
              className="accent-blue-600"
            />
            <Camera size={16} /> Camera mode (webcam + AI avatar)
          </label>
        </details>
      </SetupForm>

      {aside && <div className="md:sticky md:top-20">{aside}</div>}
    </div>
  );
}
