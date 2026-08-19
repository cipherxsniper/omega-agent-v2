import { Activity, AlertTriangle, CheckCircle2, Clock3, ShieldAlert, Wrench } from "lucide-react";

const colors = { healthy: "text-teal-200 border-teal-300/20 bg-teal-300/[0.04]", recovering: "text-amber-200 border-amber-300/20 bg-amber-300/[0.05]", approved: "text-indigo-200 border-indigo-300/20 bg-indigo-300/[0.05]", review_pending: "text-violet-200 border-violet-300/20 bg-violet-300/[0.05]", cooldown: "text-white/55 border-white/10 bg-white/[0.03]", blocked: "text-red-200 border-red-300/25 bg-red-300/[0.05]", exhausted: "text-red-200 border-red-300/25 bg-red-300/[0.05]" };

export default function SelfHealingPanel({ state }) {
  if (!state) return null;
  const status = state.state || "healthy";
  const Icon = status === "healthy" ? CheckCircle2 : status === "blocked" || status === "exhausted" ? ShieldAlert : status === "cooldown" ? Clock3 : status === "recovering" || status === "approved" ? Wrench : AlertTriangle;
  return <section className={`mx-3 mb-2 rounded-xl border p-3 ${colors[status] || colors.healthy}`} aria-label="Omega Autonomous Mission Self-Healing">
    <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-2"><Icon className="h-3.5 w-3.5" /><div><div className="text-[9px] font-mono uppercase tracking-[0.18em] opacity-70">Autonomous Self-Healing</div><div className="text-xs text-white/70">{status === "healthy" ? "No degraded dependency observed" : state.reason}</div></div></div><span className="rounded-full border border-current/25 px-2 py-0.5 text-[9px] font-mono uppercase tracking-wider">{status}</span></div>
    {state.signal && <div className="mt-2 grid grid-cols-3 gap-1.5 text-center font-mono text-[9px]"><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="opacity-45">signal</div><div className="mt-0.5 text-white/80">{state.signal.id}</div></div><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="opacity-45">playbook</div><div className="mt-0.5 text-white/80">{state.playbook?.id || "none"}</div></div><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="opacity-45">severity</div><div className="mt-0.5 text-white/80">{state.signal.severity}</div></div></div>}
    {state.playbook && <div className="mt-2 flex items-center gap-1.5 text-[9px] text-white/45"><Activity className="h-3 w-3" />registered playbook · {state.playbook.label} · {state.playbook.requiresCouncil ? "Shadow Council gated" : "safe bounded action"}</div>}
  </section>;
}
