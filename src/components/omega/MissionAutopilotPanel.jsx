import { useMemo } from "react";
import { Activity, CheckCircle2, CircleDashed, Eye, Fingerprint, GitBranch, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";

const normalizeEvents = (transcript = []) => {
  const events = [];
  transcript.forEach((entry, index) => {
    const result = entry?.result || {};
    const council = result.shadow_council;
    if (entry?.role === "assistant" && Array.isArray(entry.tool_calls)) {
      events.push({ id: `plan-${index}`, kind: "plan", title: `${entry.tool_calls.length} action${entry.tool_calls.length === 1 ? "" : "s"} proposed`, detail: "Omega emitted an observable execution plan.", status: "active", icon: GitBranch });
      entry.tool_calls.forEach((call, callIndex) => {
        events.push({ id: `task-${index}-${callIndex}`, kind: "task", title: call?.function?.name || "unknown action", detail: "Awaiting execution evidence.", status: "pending", icon: Activity });
      });
    }
    if (entry?.role === "tool") {
      const vetoed = result.error === "Shadow Council vetoed action" || council?.approved === false;
      events.push({
        id: `tool-${entry.tool_call_id || index}`,
        kind: vetoed ? "veto" : "evidence",
        title: vetoed ? "Shadow Council veto" : "Evidence received",
        detail: vetoed ? (council?.findings?.[0]?.message || "Action blocked before mutation.") : (result.output?.status_code || result.output?.status || "Observable tool result recorded."),
        status: vetoed ? "blocked" : result.success === false ? "failed" : "verified",
        icon: vetoed ? ShieldAlert : Fingerprint,
      });
    }
    if (entry?.final) {
      events.push({ id: `final-${index}`, kind: "complete", title: "Mission response verified", detail: "Final narrative returned after the observable transcript.", status: "verified", icon: CheckCircle2 });
    }
  });
  return events;
};

export default function MissionAutopilotPanel({ mission, transcript = [], isThinking }) {
  const events = useMemo(() => normalizeEvents(transcript), [transcript]);
  const verified = events.filter((event) => event.status === "verified").length;
  const blocked = events.filter((event) => event.status === "blocked" || event.status === "failed").length;
  const active = isThinking && blocked === 0;
  if (!mission) return null;

  return (
    <section className="mx-3 mb-2 rounded-xl border border-indigo-300/15 bg-indigo-300/[0.035] p-3" aria-label="Omega Mission Autopilot">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-lg border border-indigo-300/20 bg-indigo-300/10 p-1.5"><GitBranch className="h-3.5 w-3.5 text-indigo-200" /></div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-indigo-200/70">Mission Autopilot</div>
            <div className="mt-0.5 text-xs text-white/75">{active ? "Executing with live evidence" : blocked ? "Blocked pending review" : "Evidence graph available"}</div>
          </div>
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-[9px] font-mono uppercase tracking-wider ${blocked ? "border-red-300/30 text-red-200" : active ? "border-amber-300/30 text-amber-200" : "border-teal-300/30 text-teal-200"}`}>
          {blocked ? "vetoed" : active ? "live" : "verified"}
        </span>
      </div>

      <div className="mt-2 grid grid-cols-3 gap-1.5 text-center font-mono text-[9px]">
        <div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="text-white/35">events</div><div className="mt-0.5 text-white/80">{events.length}</div></div>
        <div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="text-white/35">evidence</div><div className="mt-0.5 text-teal-200">{verified}</div></div>
        <div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="text-white/35">blocked</div><div className={`mt-0.5 ${blocked ? "text-red-200" : "text-white/80"}`}>{blocked}</div></div>
      </div>

      <div className="mt-3 space-y-1.5">
        {events.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-white/5 bg-black/20 p-2 text-[10px] text-white/35"><Eye className="h-3 w-3" />Waiting for the first live mission event.</div>
        ) : events.slice(-8).map((event) => {
          const Icon = event.icon || CircleDashed;
          const color = event.status === "blocked" || event.status === "failed" ? "text-red-300" : event.status === "verified" ? "text-teal-300" : event.status === "active" ? "text-amber-200" : "text-white/35";
          return <div key={event.id} className="flex items-start gap-2 rounded-lg border border-white/5 bg-black/20 p-2">
            <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${color}`} />
            <div className="min-w-0"><div className={`text-[10px] font-medium ${color}`}>{event.title}</div><div className="mt-0.5 text-[9px] leading-relaxed text-white/35">{event.detail}</div></div>
          </div>;
        })}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-[9px] font-mono text-white/30"><span className="truncate">graph: plan → council → action → evidence</span><span className="shrink-0 text-indigo-200/60">proof:{mission.proofId?.slice(0, 10) || "pending"}</span></div>
    </section>
  );
}
