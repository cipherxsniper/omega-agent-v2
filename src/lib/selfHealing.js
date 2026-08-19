const MAX_ATTEMPTS = 2;
const COOLDOWN_MS = 30_000;

export const SELF_HEALING_STATES = Object.freeze({
  HEALTHY: "healthy",
  DEGRADED: "degraded",
  REVIEW_PENDING: "review_pending",
  APPROVED: "approved",
  RECOVERING: "recovering",
  RECOVERED: "recovered",
  COOLDOWN: "cooldown",
  BLOCKED: "blocked",
  EXHAUSTED: "exhausted",
});

export const RECOVERY_PLAYBOOKS = Object.freeze({
  reconnect_sse: Object.freeze({ id: "reconnect_sse", label: "Reconnect SSE", sideEffect: "transport-only", requiresCouncil: false }),
  replay_last_checkpoint: Object.freeze({ id: "replay_last_checkpoint", label: "Replay last checkpoint", sideEffect: "bounded-job-retry", requiresCouncil: true }),
  refresh_ledger: Object.freeze({ id: "refresh_ledger", label: "Refresh Mission Ledger", sideEffect: "local-read-only", requiresCouncil: false }),
});

export const detectDependency = ({ isThinking, eventCount = 0, recovery, ledgerStatus = "verified", now = Date.now() } = {}) => {
  if (ledgerStatus === "corrupt") return { id: "ledger_integrity", severity: "critical", reason: "Mission Ledger integrity failed; historical state is not trusted." };
  if (recovery?.status === "blocked" || recovery?.status === "exhausted") return { id: recovery.status, severity: "critical", reason: recovery.reason || "Recovery cannot continue." };
  if (isThinking && eventCount === 0 && recovery?.startedAt && now - recovery.startedAt > 30_000) return { id: "missing_sse_evidence", severity: "high", reason: "No terminal SSE evidence observed within the bounded wait window." };
  if (recovery?.status === "degraded") return { id: "degraded_dependency", severity: "high", reason: recovery.reason || "Mission dependency degraded." };
  return null;
};

export const choosePlaybook = (signal, recovery = {}) => {
  if (!signal) return null;
  if (signal.severity === "critical" || signal.id === "ledger_integrity") return null;
  if (signal.id === "missing_sse_evidence") return RECOVERY_PLAYBOOKS.replay_last_checkpoint;
  if (["degraded_dependency", "transport"].includes(signal.id)) return RECOVERY_PLAYBOOKS.reconnect_sse;
  return RECOVERY_PLAYBOOKS.refresh_ledger;
};

export const evaluateSelfHealing = ({ signal, recovery = {}, now = Date.now(), councilApproved = false } = {}) => {
  if (!signal) return { state: SELF_HEALING_STATES.HEALTHY, signal: null, playbook: null, reason: "No degraded dependency observed." };
  if (signal.severity === "critical" || recovery.ledgerStatus === "corrupt") return { state: SELF_HEALING_STATES.BLOCKED, signal, playbook: null, reason: "Critical or untrusted state requires operator intervention." };
  if ((recovery.attempts || 0) >= (recovery.maxAttempts || MAX_ATTEMPTS)) return { state: SELF_HEALING_STATES.EXHAUSTED, signal, playbook: null, reason: "Automatic recovery budget exhausted." };
  if (recovery.lastAttemptAt && now - recovery.lastAttemptAt < (recovery.cooldownMs || COOLDOWN_MS)) return { state: SELF_HEALING_STATES.COOLDOWN, signal, playbook: null, reason: "Recovery cooldown is active." };
  const playbook = choosePlaybook(signal, recovery);
  if (!playbook) return { state: SELF_HEALING_STATES.BLOCKED, signal, playbook: null, reason: "No registered safe playbook matches this dependency." };
  if (playbook.requiresCouncil && !councilApproved) return { state: SELF_HEALING_STATES.REVIEW_PENDING, signal, playbook, reason: "Shadow Council approval required before bounded replay." };
  return { state: councilApproved ? SELF_HEALING_STATES.APPROVED : SELF_HEALING_STATES.RECOVERING, signal, playbook, reason: `Executing registered playbook: ${playbook.label}.` };
};

export const beginRecovery = (decision, recovery = {}, now = Date.now()) => {
  if (![SELF_HEALING_STATES.APPROVED, SELF_HEALING_STATES.RECOVERING].includes(decision?.state)) return { ...recovery, status: decision?.state || SELF_HEALING_STATES.BLOCKED, reason: decision?.reason };
  return { ...recovery, status: SELF_HEALING_STATES.RECOVERING, attempts: (recovery.attempts || 0) + 1, maxAttempts: recovery.maxAttempts || MAX_ATTEMPTS, lastAttemptAt: now, cooldownMs: recovery.cooldownMs || COOLDOWN_MS, playbookId: decision.playbook.id, reason: decision.reason };
};
