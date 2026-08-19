import { CheckCircle2, Circle, Globe, Loader2, Terminal, Monitor, Search, Brain } from "lucide-react";

const ICONS = { browser: Globe, terminal: Terminal, search: Search, analysis: Brain, thinking: Brain, editor: Monitor };

export default function InlineActivityStrip({ transcript = [], isThinking = false, onOpenWorkspace }) {
  if (!transcript.length && !isThinking) return null;
  const steps = transcript.slice(-6);
  const completed = steps.filter((step) => step.status === "completed" || step.type === "tool_result").length;
  const active = steps.find((step) => step.status === "running") || steps[steps.length - 1];
  const activeTool = active?.tool || active?.name || active?.type || "thinking";
  const Icon = ICONS[activeTool] || Monitor;
  const preview = active?.tool_output || active?.output || active?.content || active?.description || "Omega is observing the next action...";

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-teal-300/15 bg-black/35 shadow-[0_0_24px_rgba(45,212,191,0.06)]">
      <div className="flex items-center justify-between border-b border-white/5 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-teal-300/15 text-teal-200"><Icon className="h-3 w-3" /></span>
          <span className="text-[10px] font-mono uppercase tracking-[0.14em] text-teal-100/80">Live Omega activity</span>
          {isThinking && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-teal-300" />}
        </div>
        <button type="button" onClick={onOpenWorkspace} className="text-[10px] text-teal-200/60 transition hover:text-teal-100">Open full view</button>
      </div>
      <div className="grid gap-2 p-3 sm:grid-cols-[1fr_1.15fr]">
        <div className="space-y-1.5">
          {steps.map((step, index) => {
            const done = step.status === "completed" || step.type === "tool_result";
            const StepIcon = ICONS[step.tool] || (done ? CheckCircle2 : Circle);
            return (
              <div key={step.id || `${step.type}-${index}`} className="flex min-w-0 items-center gap-2 text-[11px]">
                {done ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-teal-300" /> : step.status === "running" ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-teal-300" /> : <StepIcon className="h-3.5 w-3.5 shrink-0 text-white/25" />}
                <span className={`truncate ${done ? "text-white/60" : "text-white/85"}`}>{step.title || step.name || step.description || "Agent step"}</span>
              </div>
            );
          })}
        </div>
        <div className="min-h-[76px] rounded-lg border border-white/5 bg-white/[0.025] p-2 font-mono text-[10px] text-white/45">
          <div className="mb-1 flex items-center justify-between text-[9px] uppercase tracking-wider text-white/25"><span>{activeTool} preview</span><span>{completed}/{steps.length} complete</span></div>
          <pre className="max-h-16 overflow-auto whitespace-pre-wrap">{String(preview).slice(0, 900)}</pre>
        </div>
      </div>
    </div>
  );
}
