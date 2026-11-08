/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

export type PracticeStep = "setup" | "interview" | "report";

const STEPS: { id: PracticeStep; label: string }[] = [
  { id: "setup", label: "Setup" },
  { id: "interview", label: "Interview" },
  { id: "report", label: "Report" },
];

export function PracticeStepper({ step }: { step: PracticeStep }) {
  const activeIndex = STEPS.findIndex((s) => s.id === step);

  return (
    <div className="flex items-center gap-2" role="list" aria-label="Practice interview progress">
      {STEPS.map((s, i) => {
        const isActive = s.id === step;
        const isDone = i < activeIndex;
        return (
          <div key={s.id} className="flex items-center gap-2">
            <span
              data-testid={`practice-step-${s.id}`}
              aria-current={isActive ? "step" : undefined}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border transition-colors ${
                isActive
                  ? "bg-blue-500/15 border-blue-500/40 text-blue-400"
                  : isDone
                    ? "bg-theme-surface/60 border-theme-border text-theme-text-secondary"
                    : "bg-theme-surface/30 border-theme-border/50 text-theme-muted"
              }`}
            >
              <span className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] bg-black/10">
                {i + 1}
              </span>
              {s.label}
            </span>
            {i < STEPS.length - 1 && <span className="w-4 h-px bg-theme-border" />}
          </div>
        );
      })}
    </div>
  );
}
