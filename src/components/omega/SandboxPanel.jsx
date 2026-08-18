import React, { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  FileCode2,
  FileEdit,
  Monitor,
  Pause,
  Play,
  Terminal,
  X,
} from "lucide-react";

function describeStep(step) {
  if (!step) return null;

  if (step.role === "assistant" && step.tool_calls?.length) {
    const toolCall = step.tool_calls[0];
    const name = toolCall?.function?.name || "tool";
    let args = {};
    try {
      args = JSON.parse(toolCall?.function?.arguments || "{}");
    } catch {
      args = {};
    }

    if (name === "write_file" || name === "edit_file") {
      return {
        kind: "editor",
        icon: FileEdit,
        title: name === "write_file" ? "Creating file" : "Editing file",
        label: args.path || "Untitled file",
        path: args.path,
        content: args.content || "",
        provenance: step.decision_provenance?.[0],
      };
    }

    if (name === "run_bash") {
      return {
        kind: "terminal",
        icon: Terminal,
        title: "Running command",
        label: args.command || "Terminal command",
        command: args.command || "",
        provenance: step.decision_provenance?.[0],
      };
    }

    return {
      kind: "tool",
      icon: FileCode2,
      title: `Using ${name}`,
      label: "Agent tool call",
      args,
      provenance: step.decision_provenance?.[0],
    };
  }

  if (step.role === "tool") {
    const output = step.result?.output || {};
    if (output.path) {
      return {
        kind: "editor",
        icon: FileEdit,
        title: "File updated",
        label: output.path,
        path: output.path,
        content: output.stdout || output.content || "",
      };
    }
    if (output.command) {
      return {
        kind: "terminal",
        icon: Terminal,
        title: "Command finished",
        label: output.command,
        command: output.command,
        stdout: output.stdout || "",
        stderr: output.stderr || "",
        provenance: step.decision_provenance,
      };
    }
  }

  return null;
}

export default function SandboxPanel({
  steps = [],
  agentName = "Omega",
  onClose,
  live = true,
}) {
  const [index, setIndex] = useState(Math.max(0, steps.length - 1));
  const [tab, setTab] = useState("Modified");
  const [playing, setPlaying] = useState(live);

  const descriptors = useMemo(
    () => steps.map(describeStep).filter(Boolean),
    [steps],
  );

  useEffect(() => {
    setIndex(Math.max(0, descriptors.length - 1));
  }, [descriptors.length]);

  useEffect(() => {
    setPlaying(live);
  }, [live]);

  const current = descriptors[index] || descriptors[descriptors.length - 1];
  if (!current) return null;

  const Icon = current.icon || FileCode2;
  const stepCount = descriptors.length;
  const shownIndex = Math.min(index, Math.max(0, stepCount - 1));
  const goto = (delta) =>
    setIndex((value) => Math.min(stepCount - 1, Math.max(0, value + delta)));

  const content =
    current.kind === "editor"
      ? current.content || "No file content was included in this step."
      : [current.command, current.stdout, current.stderr]
          .filter(Boolean)
          .join("\n") || "Waiting for terminal output…";

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#090a0b] text-white">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.08] bg-[#101112] px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close computer view"
            className="rounded-lg p-2 text-white/50 transition hover:bg-white/[0.07] hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Monitor className="h-4 w-4 text-teal-300" />
              <span>{agentName}&apos;s computer</span>
              <span className="hidden text-white/25 sm:inline">/</span>
              <span className="hidden truncate text-xs text-white/45 sm:inline">
                Live workspace
              </span>
            </div>
          </div>
        </div>
        <button
          type="button"
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-white/70 transition hover:bg-white/[0.08] hover:text-white"
        >
          <Monitor className="h-3.5 w-3.5" />
          This computer
          <ChevronDown className="h-3.5 w-3.5 text-white/40" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden px-3 py-4 sm:px-6 sm:py-6">
        <div className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-white/[0.09] bg-[#0f1011] shadow-2xl shadow-black/30">
          <div className="flex h-11 shrink-0 items-center justify-between border-b border-white/[0.08] bg-[#151617] px-4 text-xs">
            <div className="flex min-w-0 items-center gap-2 text-white/55">
              <Icon className="h-3.5 w-3.5 text-teal-300" />
              <span className="truncate font-mono">{current.path || current.kind}</span>
            </div>
            <span className="ml-3 shrink-0 text-white/30">
              {shownIndex + 1} / {stepCount}
            </span>
          </div>

          <div className="min-h-0 flex-1 overflow-auto bg-[#0a0b0c] p-4 sm:p-6">
            <pre className="min-h-full whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-white/75">
              {content}
            </pre>
          </div>

          {current.provenance && (
            <div className="border-t border-white/[0.08] bg-[#0d0e0f] px-4 py-3 text-xs">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-white/45">
                <span className="font-mono uppercase tracking-[0.14em] text-teal-200/70">Decision proof</span>
                <span>Observable action: <strong className="font-medium text-white/75">{current.provenance.action_chosen || current.kind}</strong></span>
                <span>Step {current.provenance.step ?? shownIndex + 1}</span>
                {current.provenance.context_hash && <span className="font-mono text-white/30">ctx:{current.provenance.context_hash.slice(0, 10)}</span>}
              </div>
              <div className="mt-1 text-white/30">Recorded action metadata; hidden chain-of-thought is not displayed.</div>
            </div>
          )}

          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-white/[0.08] bg-[#121314] px-4 py-3">
            <div className="flex items-center gap-1 rounded-lg bg-white/[0.04] p-1">
              {(current.kind === "editor" ? ["Diff", "Original", "Modified"] : ["Output"]).map(
                (item) => (
                  <button
                    type="button"
                    key={item}
                    onClick={() => setTab(item)}
                    className={`rounded-md px-3 py-1.5 text-xs transition ${
                      tab === item
                        ? "bg-white/[0.1] text-white"
                        : "text-white/40 hover:text-white/70"
                    }`}
                  >
                    {item}
                  </button>
                ),
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-white/40">
              <Circle className={`h-2.5 w-2.5 fill-current ${live ? "text-teal-300" : "text-white/25"}`} />
              {live ? "Live trace" : "Trace complete"}
            </div>
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-white/[0.08] bg-[#101112] px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-400/10 text-teal-300">
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-white/90">{current.title}</div>
            <div className="truncate text-xs text-white/45">{current.label}</div>
          </div>
          <span className="hidden text-xs tabular-nums text-white/30 sm:inline">
            Step {shownIndex + 1} of {stepCount}
          </span>
        </div>

        <div className="mx-auto mt-3 flex max-w-6xl items-center gap-3">
          <button
            type="button"
            onClick={() => goto(-1)}
            disabled={shownIndex === 0}
            aria-label="Previous step"
            className="rounded-lg p-2 text-white/45 transition hover:bg-white/[0.07] hover:text-white disabled:cursor-not-allowed disabled:opacity-25"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <input
            type="range"
            min={0}
            max={Math.max(0, stepCount - 1)}
            value={shownIndex}
            onChange={(event) => setIndex(Number(event.target.value))}
            aria-label="Trace timeline"
            className="h-1 min-w-0 flex-1 cursor-pointer accent-teal-400"
          />
          <button
            type="button"
            onClick={() => goto(1)}
            disabled={shownIndex === stepCount - 1}
            aria-label="Next step"
            className="rounded-lg p-2 text-white/45 transition hover:bg-white/[0.07] hover:text-white disabled:cursor-not-allowed disabled:opacity-25"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setPlaying((value) => !value)}
            aria-label={playing ? "Pause live trace" : "Resume live trace"}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-white/70 transition hover:bg-white/[0.08] hover:text-white"
          >
            {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">{playing ? "Pause" : "Resume"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
