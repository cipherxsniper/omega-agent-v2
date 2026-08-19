const STORAGE_KEY = "omega_mission_ledger_v1";
const MAX_MISSIONS = 50;
const MAX_EVENTS = 500;
const SCHEMA_VERSION = 1;

const canonical = (value) => JSON.stringify(value, Object.keys(value).sort());

const digest = async (value) => {
  const bytes = new TextEncoder().encode(canonical(value));
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
};

const read = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const write = (events) => localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-MAX_EVENTS)));

export const redactMissionEvent = (event = {}) => ({
  missionId: String(event.missionId || "").slice(0, 100),
  proofId: String(event.proofId || "").slice(0, 128),
  type: String(event.type || "observed").slice(0, 40),
  status: String(event.status || "observed").slice(0, 30),
  step: String(event.step || event.lastStep || "").slice(0, 160),
  objective: String(event.objective || "").slice(0, 180),
  task: String(event.task || "").slice(0, 120),
  evidenceHash: String(event.evidenceHash || "").slice(0, 128),
  reason: String(event.reason || "").slice(0, 240),
  eventCount: Number.isFinite(event.eventCount) ? event.eventCount : 0,
});

let appendQueue = Promise.resolve();
export const appendMissionEvent = (event) => {
  appendQueue = appendQueue.then(async () => {
    const events = read();
    const payload = redactMissionEvent(event);
    const record = {
      schema: SCHEMA_VERSION,
      eventId: `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`,
      createdAt: new Date().toISOString(),
      previousHash: events.at(-1)?.receiptHash || null,
      payload,
    };
    record.receiptHash = await digest(record);
    write([...events, record]);
    return record;
  });
  return appendQueue;
};

export const hydrateMissionLedger = async () => {
  const events = read();
  if (!events.length) return { status: "empty", events: [], missions: [] };
  let previous = null;
  for (const record of events) {
    if (record.schema !== SCHEMA_VERSION || record.previousHash !== previous) return { status: "corrupt", events: [], missions: [] };
    const { receiptHash, ...unsigned } = record;
    if (await digest(unsigned) !== receiptHash) return { status: "corrupt", events: [], missions: [] };
    previous = receiptHash;
  }
  const grouped = new Map();
  for (const record of events) {
    const payload = record.payload || {};
    if (!payload.missionId) continue;
    const mission = grouped.get(payload.missionId) || { id: payload.missionId, proofId: payload.proofId, objective: payload.objective || "Recovered mission", status: "observed", events: [], transcript: [] };
    mission.events.push({ ...payload, receiptHash: record.receiptHash, createdAt: record.createdAt });
    if (payload.type === "mission_started") mission.status = "active";
    if (payload.type === "mission_completed" || payload.type === "recovered") mission.status = "verified";
    if (payload.type === "degraded") mission.status = "degraded";
    if (payload.type === "blocked" || payload.type === "exhausted") mission.status = "blocked";
    if (payload.type === "sse_step") mission.transcript.push({ role: "tool", title: payload.step, result: { output: { evidence_hash: payload.evidenceHash } } });
    grouped.set(payload.missionId, mission);
  }
  return { status: "verified", events, missions: Array.from(grouped.values()).slice(-MAX_MISSIONS), head: previous };
};

export const clearMissionLedger = () => localStorage.removeItem(STORAGE_KEY);
export { STORAGE_KEY, MAX_MISSIONS, MAX_EVENTS };
