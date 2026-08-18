import React, { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { stepsFromTranscript } from "@/lib/transcriptAdapter";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe, Terminal, FileCode, ListChecks, Loader2, CheckCircle,
  XCircle, Clock, Search, Brain, Code, Monitor,
} from "lucide-react";
import MissionControl from "@/components/omega/MissionControl";
import MissionAutopilotPanel from "@/components/omega/MissionAutopilotPanel";
import MissionGraph from "@/components/omega/MissionGraph";
import MissionRecoveryPanel from "@/components/omega/MissionRecoveryPanel";
import MissionLedgerPanel from "@/components/omega/MissionLedgerPanel";
import SelfHealingPanel from "@/components/omega/SelfHealingPanel";
import FederatedSwarmPanel from "@/components/omega/FederatedSwarmPanel";

const TABS = [
  { id: "actions", label: "Actions", icon: ListChecks },
  { id: "browser", label: "Browser", icon: Globe },
  { id: "terminal", label: "Terminal", icon: Terminal },
  { id: "files", label: "Files", icon: FileCode },
];

const TOOL_ICONS = {
  browser: Globe,
  terminal: Terminal,
  editor: FileCode,
  search: Search,
  analysis: Brain,
  thinking: Brain,
  none: Code,
};

export default function WorkspacePanel({ conversationId, isThinking, onClose, transcript, mission, missions = [], recovery, onReplay, ledger, selfHealing, swarm }) {
  const [activeTab, setActiveTab] = useState("actions");
  const [steps, setSteps] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (transcript) {
      setSteps(stepsFromTranscript(transcript));
      setLoading(false);
      return;
    }
    if (conversationId) loadSteps(conversationId);
  }, [conversationId, isThinking, transcript]);

  // Realtime subscribe to steps (legacy path — inactive while transcript is supplied directly)
  useEffect(() => {
    if (transcript) return;
    if (!conversationId) return;
    const unsub = base44.entities.AgentStep.subscribe((event) => {
      if (event.data?.conversation_id !== conversationId) return;
      loadSteps(conversationId);
    });
    return unsub;
  }, [conversationId, transcript]);

  const loadSteps = async (convId) => {
    setLoading(true);
    const data = await base44.entities.AgentStep.filter(
      { conversation_id: convId },
      "step_number",
      100
    );
    setSteps(data);
    setLoading(false);
  };

  const runningStep = steps.find((s) => s.status === "running");
  const lastBrowserStep = [...steps].reverse().find((s) => s.tool === "browser" && s.tool_url);
  const lastTerminalStep = [...steps].reverse().find((s) => s.tool === "terminal" && s.tool_output);
  const fileSteps = steps.filter((s) => s.tool === "editor");

  const completedCount = steps.filter((s) => s.status === "completed").length;
  const progressPercent = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;

  return (
    <div className="h-full flex flex-col bg-black border-l border-white/5">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-white/5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-teal-400" />
          <span className="text-white text-sm font-medium">Omega Workspace</span>
        </div>
        {isThinking && (
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-[10px] text-teal-400 font-mono uppercase tracking-wider">Live</span>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {steps.length > 0 && (
        <div className="px-3 py-1.5 border-b border-white/5 bg-white/[0.01]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] text-white/30 font-mono uppercase tracking-wider">
              {isThinking ? "Working" : "Complete"} · {completedCount}/{steps.length} steps
            </span>
            <span className="text-[9px] text-teal-400 font-mono">{progressPercent}%</span>
          </div>
          <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-teal-400"
              animate={{ width: `${progressPercent}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>
      )}

      <MissionControl mission={mission} steps={steps} isThinking={isThinking} />
      <MissionAutopilotPanel mission={mission} transcript={transcript || []} isThinking={isThinking} />
      <MissionGraph mission={mission} missions={missions} transcript={transcript || []} isThinking={isThinking} />
      <MissionRecoveryPanel recovery={recovery} onReplay={onReplay} isThinking={isThinking} />
      <MissionLedgerPanel ledger={ledger} />
      <SelfHealingPanel state={selfHealing} />
      <FederatedSwarmPanel swarm={swarm} />

      {/* Tabs */}
      <div className="flex border-b border-white/5 shrink-0">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs transition-colors ${
                activeTab === tab.id
                  ? "text-teal-400 border-b border-teal-400"
                  : "text-white/30 hover:text-white/50 border-b border-transparent"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          {activeTab === "actions" && (
            <motion.div key="actions" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="p-3 space-y-1">
              {loading && steps.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 text-teal-400 animate-spin" />
                </div>
              ) : steps.length === 0 ? (
                <div className="text-center py-12">
                  <ListChecks className="w-8 h-8 text-white/10 mx-auto mb-2" />
                  <p className="text-white/30 text-xs">No actions yet</p>
                  <p className="text-white/15 text-[10px] mt-1">Steps appear as Omega works</p>
                </div>
              ) : (
                steps.map((step, i) => {
                  const Icon = TOOL_ICONS[step.tool] || Code;
                  return (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className={`relative pl-6 py-2 ${i !== steps.length - 1 ? "border-l border-white/5" : ""}`}
                    >
                      {/* Step dot/icon */}
                      <div className="absolute left-0 top-2.5 -translate-x-[7px]">
                        {step.status === "running" ? (
                          <Loader2 className="w-3.5 h-3.5 text-teal-400 animate-spin" />
                        ) : step.status === "completed" ? (
                          <CheckCircle className="w-3.5 h-3.5 text-teal-400" />
                        ) : step.status === "failed" ? (
                          <XCircle className="w-3.5 h-3.5 text-red-400" />
                        ) : (
                          <div className="w-3.5 h-3.5 rounded-full border border-white/20" />
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <Icon className={`w-3 h-3 ${step.status === "running" ? "text-teal-400" : "text-white/30"}`} />
                        <span className={`text-xs font-medium ${step.status === "pending" ? "text-white/30" : "text-white/80"}`}>
                          {step.title}
                        </span>
                      </div>
                      {step.description && (
                        <p className="text-[11px] text-white/30 ml-4">{step.description}</p>
                      )}
                      {step.decision_provenance && (
                        <div className="ml-4 mt-1 flex items-center gap-2 text-[9px] font-mono uppercase tracking-[0.12em] text-teal-200/45">
                          <span className="rounded border border-teal-300/15 px-1.5 py-0.5">proof linked</span>
                          {step.decision_provenance.context_hash && <span>ctx:{step.decision_provenance.context_hash.slice(0, 8)}</span>}
                        </div>
                      )}
                      {step.duration_ms && step.status === "completed" && (
                        <p className="text-[9px] text-white/15 ml-4 font-mono">{(step.duration_ms / 1000).toFixed(1)}s</p>
                      )}
                    </motion.div>
                  );
                })
              )}
            </motion.div>
          )}

          {activeTab === "browser" && (
            <motion.div key="browser" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col h-full">
              {lastBrowserStep ? (
                <>
                  {/* Browser chrome */}
                  <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 bg-white/[0.02]">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 rounded-full bg-red-500/40" />
                      <div className="w-2 h-2 rounded-full bg-yellow-500/40" />
                      <div className="w-2 h-2 rounded-full bg-green-500/40" />
                    </div>
                    <div className="flex-1 bg-white/5 rounded-md px-2 py-1 flex items-center gap-1.5 min-w-0">
                      <Globe className="w-3 h-3 text-white/30 shrink-0" />
                      <span className="text-[11px] text-white/40 truncate font-mono">{lastBrowserStep.tool_url}</span>
                    </div>
                  </div>
                  {/* Browser content */}
                  <div className="flex-1 p-4 overflow-y-auto">
                    <h3 className="text-white text-sm font-bold mb-2">{lastBrowserStep.title}</h3>
                    {lastBrowserStep.tool_output ? (
                      <p className="text-white/50 text-xs leading-relaxed whitespace-pre-wrap">{lastBrowserStep.tool_output}</p>
                    ) : (
                      <p className="text-white/20 text-xs">Loading page...</p>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full">
                  <Globe className="w-10 h-10 text-white/10 mb-2" />
                  <p className="text-white/30 text-xs">Browser idle</p>
                  <p className="text-white/15 text-[10px] mt-1">Omega browses the web during research</p>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === "terminal" && (
            <motion.div key="terminal" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="h-full">
              <div className="h-full bg-black font-mono text-xs p-3 overflow-y-auto">
                <div className="text-white/20 mb-2">Omega Terminal — omegaagent$</div>
                {steps.length === 0 ? (
                  <p className="text-white/20">omegaagent$ waiting for command...</p>
                ) : (
                  steps.map((s) => (
                    <div key={s.id} className="mb-2">
                      <div className="text-teal-400">
                        omegaagent$ <span className="text-white/70">{s.title}</span>
                        {s.description && <span className="text-white/30"> — {s.description}</span>}
                      </div>
                      {s.tool_output && (
                        <pre className="text-white/50 whitespace-pre-wrap mt-0.5">{s.tool_output}</pre>
                      )}
                    </div>
                  ))
                )}
                {isThinking && runningStep && (
                  <div className="text-teal-400 flex items-center gap-1">
                    omegaagent$ <span className="animate-pulse">█</span>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === "files" && (
            <motion.div key="files" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="p-3">
              {fileSteps.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <FileCode className="w-10 h-10 text-white/10 mb-2" />
                  <p className="text-white/30 text-xs">No files created</p>
                  <p className="text-white/15 text-[10px] mt-1">Files appear when Omega writes code</p>
                </div>
              ) : (
                fileSteps.map((f) => (
                  <div key={f.id} className="mb-2 p-2 rounded-lg border border-white/5 bg-white/[0.02]">
                    <div className="flex items-center gap-2 mb-1">
                      <FileCode className="w-3.5 h-3.5 text-teal-400" />
                      <span className="text-white/80 text-xs font-mono">{f.title}</span>
                    </div>
                    {f.tool_output && (
                      <pre className="text-[10px] text-white/40 font-mono whitespace-pre-wrap mt-1 max-h-32 overflow-y-auto">{f.tool_output}</pre>
                    )}
                  </div>
                ))
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}