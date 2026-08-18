import React from "react";
import { CheckCircle2, CircleDashed, Fingerprint, ShieldCheck, Target } from "lucide-react";

export default function MissionControl({ mission, steps = [], isThinking }) {
  if (!mission) return null;

  const completed = steps.filter((step) => step.status === "completed").length;
  const failed = steps.filter((step) => step.status === "failed").length;
  const criteriaComplete = mission.criteria.map((criterion, index) => ({
    ...criterion,
    complete: !isThinking && failed === 0 && (index === 0 ? completed > 0 : completed >= Math.max(1, steps.length)),
  }));
  const allComplete = !isThinking && failed === 0 && criteriaComplete.every((criterion) => criterion.complete);

  return (
    <section className="mx-3 mt-3 mb-2 rounded-xl border border-teal-300/15 bg-teal-300/[0.035] p-3" aria-label="Omega Mission Control">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-lg border border-teal-300/20 bg-teal-300/10 p-1.5">
            <Target className="h-3.5 w-3.5 text-teal-300" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-teal-200/70">Mission Control</div>
            <div className="mt-0.5 text-xs font-medium text-white/85">{mission.objective}</div>
          </div>
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-[9px] font-mono uppercase tracking-wider ${allComplete ? "border-teal-300/30 text-teal-200" : failed ? "border-red-300/30 text-red-200" : "border-amber-300/20 text-amber-200/80"}`}>
          {allComplete ? "verified" : failed ? "blocked" : isThinking ? "active" : "ready"}
        </span>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-white/5 bg-black/20 p-2">
          <div className="mb-1 flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-white/35"><ShieldCheck className="h-3 w-3" /> acceptance</div>
          <div className="space-y-1.5">
            {criteriaComplete.map((criterion) => (
              <div key={criterion.label} className="flex items-start gap-1.5 text-[10px] text-white/60">
                {criterion.complete ? <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-teal-300" /> : <CircleDashed className="mt-0.5 h-3 w-3 shrink-0 text-white/25" />}
                <span>{criterion.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-white/5 bg-black/20 p-2">
          <div className="mb-1 flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-white/35"><Fingerprint className="h-3 w-3" /> evidence contract</div>
          <div className="space-y-1 text-[10px] text-white/55">
            {mission.evidence.map((item) => <div key={item} className="flex gap-1.5"><span className="text-teal-300/70">•</span><span>{item}</span></div>)}
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-[9px] font-mono text-white/30">
        <span className="truncate">boundary: {mission.boundary}</span>
        <span className="shrink-0 text-teal-200/60">proof:{mission.proofId.slice(0, 10)}</span>
      </div>
    </section>
  );
}
