import { AlertTriangle, CheckCircle2, History, Loader2, RotateCcw, ShieldCheck } from "lucide-react";

const tone = {
  checkpointed: "border-indigo-300/20 bg-indigo-300/[0.05] text-indigo-200",
  degraded: "border-amber-300/25 bg-amber-300/[0.06] text-amber-200",
  replay_pending: "border-violet-300/25 bg-violet-300/[0.06] text-violet-200",
  replaying: "border-amber-300/25 bg-amber-300/[0.06] text-amber-200",
  recovered: "border-teal-300/25 bg-teal-300/[0.06] text-teal-200",
  exhausted: "border-red-300/25 bg-red-300/[0.06] text-red-200",
};

export default function MissionRecoveryPanel({ recovery, onReplay, isThinking }) {
  if (!recovery) return null;
  const status = recovery.status || "checkpointed";
  const Icon = status === "recovered" ? CheckCircle2 : status === "replaying" ? Loader2 : status === "degraded" || status === "exhausted" ? AlertTriangle : History;
  const canReplay = (status === "degraded" || status === "checkpointed") && !isThinking && (recovery.attempts || 0) < (recovery.maxAttempts || 2) && recovery.text;
  return <section className={`mx-3 mb-2 rounded-xl border p-3 ${tone[status] || tone.checkpointed}`} aria-label="Omega Mission Replay and Recovery">
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-2"><Icon className={`h-3.5 w-3.5 ${status === "replaying" ? "animate-spin" : ""}`} /><div><div className="text-[9px] font-mono uppercase tracking-[0.18em] opacity-70">Mission Replay &amp; Recovery</div><div className="mt-0.5 text-xs text-white/75">{status === "recovered" ? "Recovered from a verified checkpoint" : status === "degraded" ? "Evidence path needs attention" : status === "exhausted" ? "Recovery budget exhausted" : "Checkpoint preserved"}</div></div></div>
      <span className="rounded-full border border-current/25 px-2 py-0.5 text-[9px] font-mono uppercase tracking-wider">{status}</span>
    </div>
    <div className="mt-2 grid grid-cols-3 gap-1.5 text-center font-mono text-[9px]"><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="opacity-45">events</div><div className="mt-0.5 text-white/80">{recovery.eventCount || 0}</div></div><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="opacity-45">retries</div><div className="mt-0.5 text-white/80">{recovery.attempts || 0}/{recovery.maxAttempts || 2}</div></div><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="opacity-45">proof</div><div className="mt-0.5 text-white/80">{recovery.proofId ? recovery.proofId.slice(0, 8) : "pending"}</div></div></div>
    <div className="mt-2 flex items-start gap-1.5 text-[9px] leading-relaxed text-white/45"><ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />{recovery.reason || "The last verified checkpoint remains available."}</div>
    {canReplay && <button type="button" onClick={onReplay} className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-current/25 px-2.5 py-1.5 text-[10px] font-medium text-current transition hover:bg-white/10"><RotateCcw className="h-3 w-3" />Replay from checkpoint</button>}
  </section>;
}
