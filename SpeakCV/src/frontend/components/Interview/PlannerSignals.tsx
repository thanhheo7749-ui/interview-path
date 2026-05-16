/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

interface PlannerSignalsProps {
  currentFocus?: string;
  whySelected?: string;
  nextSkill?: string;
  liveCues?: string[];
}

const formatLabel = (value?: string) => {
  if (!value) return "";

  return value
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const cuePalette = [
  "bg-blue-500/10 text-blue-300 border-blue-500/20",
  "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  "bg-violet-500/10 text-violet-300 border-violet-500/20",
  "bg-amber-500/10 text-amber-300 border-amber-500/20",
];

export function PlannerSignals({
  currentFocus,
  whySelected,
  nextSkill,
  liveCues = [],
}: PlannerSignalsProps) {
  const focus = formatLabel(currentFocus);
  const why = formatLabel(whySelected);
  const next = formatLabel(nextSkill);
  const cues = liveCues.filter(Boolean);

  if (!focus && !why && !next && cues.length === 0) {
    return null;
  }

  return (
    <section className="w-full max-w-6xl z-10 mb-6 animate-in fade-in slide-in-from-bottom-2">
      <div className="bg-theme-primary/70 border border-theme-border/40 rounded-3xl px-5 py-4 backdrop-blur-md shadow-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3 min-w-0">
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-400">
              Interview focus
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <SignalItem label="Current focus" value={focus} />
              <SignalItem label="Why this question" value={why} />
              <SignalItem label="Next skill" value={next} />
            </div>
          </div>

          {cues.length > 0 && (
            <div className="md:max-w-sm min-w-0">
              <div className="text-xs font-bold uppercase tracking-[0.2em] text-theme-text-secondary mb-2">
                Live cues
              </div>
              <div className="flex flex-wrap gap-2">
                {cues.map((cue, index) => (
                  <span
                    key={`${cue}-${index}`}
                    className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${cuePalette[index % cuePalette.length]}`}
                  >
                    {cue}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function SignalItem({ label, value }: { label: string; value?: string }) {
  return (
    <div className="min-w-0 rounded-2xl border border-theme-border/30 bg-theme-primary/40 px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-theme-muted mb-1">
        {label}
      </div>
      <div className="text-sm text-theme-text leading-relaxed break-words">
        {value || "Waiting for the next signal..."}
      </div>
    </div>
  );
}
