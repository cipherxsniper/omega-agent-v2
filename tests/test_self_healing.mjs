import assert from "node:assert/strict";
import { SELF_HEALING_STATES, choosePlaybook, detectDependency, evaluateSelfHealing } from "../src/lib/selfHealing.js";

const now = Date.now();
const signal = detectDependency({ isThinking: true, eventCount: 0, recovery: { startedAt: now - 31_000 }, now });
assert.equal(signal.id, "missing_sse_evidence");
assert.equal(choosePlaybook(signal).id, "replay_last_checkpoint");
assert.equal(evaluateSelfHealing({ signal, recovery: { attempts: 0 }, now }).state, SELF_HEALING_STATES.REVIEW_PENDING);
assert.equal(evaluateSelfHealing({ signal, recovery: { attempts: 2 }, now }).state, SELF_HEALING_STATES.EXHAUSTED);
assert.equal(evaluateSelfHealing({ signal, recovery: { attempts: 0, lastAttemptAt: now - 1000 }, now }).state, SELF_HEALING_STATES.COOLDOWN);
assert.equal(evaluateSelfHealing({ signal: { id: "ledger_integrity", severity: "critical" }, now }).state, SELF_HEALING_STATES.BLOCKED);
assert.equal(evaluateSelfHealing({ signal: null, now }).state, SELF_HEALING_STATES.HEALTHY);
console.log("SELF_HEALING_SMOKE_OK");
