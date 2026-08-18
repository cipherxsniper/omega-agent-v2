import { useMemo, useState } from "react";
import { CheckCircle2, CircleDashed, GitBranch, Loader2, ShieldAlert, ShieldCheck, Target } from "lucide-react";

const statusTone = {
  verified: { border: "border-teal-300/35", bg: "bg-teal-300/10", text: "text-teal-200", icon: CheckCircle2 },
  active: { border: "border-amber-300/35", bg: "bg-amber-300/10", text: "text-amber-200", icon: Loader2 },
  blocked: { border: "border-red-300/35", bg: "bg-red-300/10", text: "text-red-200", icon: ShieldAlert },
  pending: { border: "border-white/10", bg: "bg-white/[0.03]", text: "text-white/45", icon: CircleDashed },
};

const deriveTasks = (mission, transcript = []) => {
  const calls = transcript.flatMap((entry) => entry?.role === "assistant" && Array.isArray(entry.tool_calls) ? entry.tool_calls : []);
  const results = transcript.filter((entry) => entry?.role === "tool");
  if (Array.isArray(mission?.tasks) && mission.tasks.length) return mission.tasks;
  if (!calls.length && Array.isArray(mission?.events) && mission.events.length) {
    const durableEvents = mission.events.filter((event) => ["sse_step", "recovered", "degraded", "blocked", "exhausted"].includes(event.type));
    return durableEvents.map((event, index) => ({
      id: `${mission?.id || "mission"}-ledger-task-${index}`,
      title: event.step || (event.type === "recovered" ? "Mission response verified" : event.type.replaceAll("_", " ")),
      description: event.reason || (event.type === "sse_step" ? "Observed checkpoint from durable ledger" : "Durable mission state"),
      status: ["recovered"].includes(event.type) ? "verified" : ["blocked", "exhausted", "degraded"].includes(event.type) ? "blocked" : event.status === "checkpointed" ? "verified" : "pending",
      dependency: index > 0 ? `${mission?.id || "mission"}-ledger-task-${index - 1}` : null,
      receipt: event.receiptHash || event.evidenceHash || null,
    }));
  }
  return calls.map((call, index) => {
    const result = results[index]?.result || {};
    const blocked = result.error === "Shadow Council vetoed action" || result.shadow_council?.approved === false;
    const complete = result.success === true;
    return {
      id: `${mission?.id || "mission"}-task-${index}`,
      title: call?.function?.name || `Mission task ${index + 1}`,
      description: blocked ? "Blocked by Shadow Council" : complete ? "Evidence received" : "Awaiting execution",
      status: blocked ? "blocked" : complete ? "verified" : index === calls.length - 1 ? "active" : "pending",
      dependency: index > 0 ? `${mission?.id || "mission"}-task-${index - 1}` : null,
      receipt: result.shadow_council?.receipt_hash || result.output?.evidence_hash || null,
    };
  });
};

export default function MissionGraph({ mission, missions = [], transcript = [], isThinking }) {
  const [selected, setSelected] = useState(null);
  const allMissions = useMemo(() => {
    const source = missions.length ? missions : mission ? [mission] : [];
    return source.filter(Boolean).map((item) => ({ ...item, graphTasks: deriveTasks(item, item.id === mission?.id ? transcript : (item.transcript || [])) }));
  }, [mission, missions, transcript]);

  if (!allMissions.length) return null;
  const selectedNode = allMissions.flatMap((item) => item.graphTasks.map((task) => ({ ...task, mission: item }))).find((item) => item.id === selected);
  const activeMissions = allMissions.filter((item) => item.id === mission?.id || item.status === "active").length;
  const blockedMissions = allMissions.filter((item) => item.status === "blocked" || item.graphTasks.some((task) => task.status === "blocked")).length;

  return (
    <section className="mx-3 mb-2 rounded-xl border border-violet-300/15 bg-violet-300/[0.035] p-3" aria-label="Omega Mission Graph">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-lg border border-violet-300/20 bg-violet-300/10 p-1.5"><GitBranch className="h-3.5 w-3.5 text-violet-200" /></div>
          <div><div className="text-[9px] font-mono uppercase tracking-[0.18em] text-violet-200/70">Mission Graph</div><div className="mt-0.5 text-xs text-white/70">Concurrency and dependency topology</div></div>
        </div>
        <div className="text-right font-mono text-[9px] text-white/35"><div>{activeMissions} active</div><div className={blockedMissions ? "text-red-200/80" : "text-teal-200/70"}>{blockedMissions} blocked</div></div>
      </div>

      <div className="mt-3 space-y-3 overflow-x-auto pb-1">
        {allMissions.map((item) => {
          const missionStatus = item.id === mission?.id && isThinking ? "active" : item.status || (item.completedAt ? "verified" : "pending");
          const laneTone = statusTone[missionStatus] || statusTone.pending;
          return <div key={item.id} className="min-w-[300px] rounded-lg border border-white/5 bg-black/20 p-2">
            <div className="flex items-center gap-2 border-b border-white/5 pb-2"><Target className={`h-3.5 w-3.5 ${laneTone.text}`} /><span className="min-w-0 flex-1 truncate text-[10px] font-medium text-white/75">{item.objective}</span><span className={`rounded border px-1.5 py-0.5 font-mono text-[8px] uppercase ${laneTone.border} ${laneTone.text}`}>{missionStatus}</span></div>
            <div className="mt-2 flex items-start gap-0">
              {item.graphTasks.length ? item.graphTasks.map((task, index) => {
                const tone = statusTone[task.status] || statusTone.pending;
                const Icon = tone.icon;
                return <div key={task.id} className="flex min-w-[118px] flex-1 items-start">
                  {index > 0 && <div className="mt-4 h-px w-3 shrink-0 bg-violet-300/25" />}
                  <button type="button" onClick={() => setSelected(task.id)} className={`min-h-[62px] w-full rounded-md border p-2 text-left transition hover:brightness-125 ${tone.border} ${tone.bg}`}>
                    <div className="flex items-center gap-1.5"><Icon className={`h-3 w-3 ${tone.text} ${task.status === "active" ? "animate-spin" : ""}`} /><span className="truncate text-[9px] font-medium text-white/75">{task.title}</span></div>
                    <div className="mt-1 line-clamp-2 text-[8px] leading-relaxed text-white/35">{task.description || "Dependency node"}</div>
                  </button>
                </div>;
              }) : <div className="flex items-center gap-2 py-3 text-[9px] text-white/30"><CircleDashed className="h-3 w-3" />No task topology observed yet.</div>}
            </div>
          </div>;
        })}
      </div>

      {selectedNode && <div className="mt-2 rounded-lg border border-violet-300/15 bg-violet-300/[0.06] p-2"><div className="flex items-center gap-2 text-[9px] font-mono uppercase tracking-wider text-violet-200/70"><ShieldCheck className="h-3 w-3" /> selected node evidence</div><div className="mt-1 text-[10px] text-white/70">{selectedNode.title}</div><div className="mt-1 text-[9px] text-white/35">{selectedNode.description}</div><div className="mt-1 break-all font-mono text-[8px] text-violet-200/55">receipt: {selectedNode.receipt || "pending"}</div></div>}
      <div className="mt-2 text-[8px] font-mono text-white/25">Dependency rule: a branch advances left-to-right only after its predecessor emits observable evidence.</div>
    </section>
  );
}
