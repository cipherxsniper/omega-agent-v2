const SCHEMA_VERSION = 1;
const FRESHNESS_MS = 60_000;
const QUORUM = 2;

const encode = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const decode = (value) => Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
const canonical = (value) => JSON.stringify(value, Object.keys(value).sort());
const digest = async (value) => {
  const data = new TextEncoder().encode(canonical(value));
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
};

export const createNodeIdentity = async () => {
  const keyPair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const publicKeyJwk = await crypto.subtle.exportKey("jwk", keyPair.publicKey);
  const nodeId = (await digest(publicKeyJwk)).slice(0, 16);
  return { nodeId, keyPair, publicKeyJwk };
};

export const createSignedObservation = async (identity, payload) => {
  const body = {
    schema: SCHEMA_VERSION,
    nodeId: identity.nodeId,
    createdAt: new Date().toISOString(),
    payload: {
      missionId: String(payload.missionId || "").slice(0, 100),
      signal: String(payload.signal || "healthy").slice(0, 60),
      proposal: String(payload.proposal || "refresh_ledger").slice(0, 80),
      severity: String(payload.severity || "low").slice(0, 20),
    },
    publicKeyJwk: identity.publicKeyJwk,
  };
  const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, identity.keyPair.privateKey, new TextEncoder().encode(canonical(body)));
  return { ...body, signature: encode(signature), observationId: await digest(body) };
};

export const verifyObservation = async (observation, now = Date.now()) => {
  if (!observation || observation.schema !== SCHEMA_VERSION || !observation.nodeId || !observation.publicKeyJwk || !observation.signature) return { valid: false, reason: "malformed_observation" };
  const age = now - Date.parse(observation.createdAt);
  if (!Number.isFinite(age) || age < -5000 || age > FRESHNESS_MS) return { valid: false, reason: "stale_observation" };
  const expectedNodeId = (await digest(observation.publicKeyJwk)).slice(0, 16);
  if (expectedNodeId !== observation.nodeId) return { valid: false, reason: "node_identity_mismatch" };
  try {
    const publicKey = await crypto.subtle.importKey("jwk", observation.publicKeyJwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
    const { signature, observationId, ...body } = observation;
    const valid = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, publicKey, decode(signature), new TextEncoder().encode(canonical(body)));
    return { valid, reason: valid ? "verified" : "invalid_signature", ageMs: age };
  } catch {
    return { valid: false, reason: "invalid_key" };
  }
};

export const coordinateSwarm = async (observations = [], now = Date.now()) => {
  const verified = [];
  const rejected = [];
  for (const observation of observations) {
    const result = await verifyObservation(observation, now);
    if (result.valid) verified.push({ observation, verification: result });
    else rejected.push({ observation, reason: result.reason });
  }
  const unique = [...new Map(verified.map((item) => [item.observation.nodeId, item])).values()];
  const groups = new Map();
  for (const item of unique) {
    const key = `${item.observation.payload.signal}:${item.observation.payload.proposal}`;
    groups.set(key, [...(groups.get(key) || []), item]);
  }
  const ranked = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  if (!ranked.length) return { state: "awaiting_observations", quorum: 0, required: QUORUM, verified: [], rejected };
  const [key, support] = ranked[0];
  const conflict = ranked.length > 1 && ranked[1][1].length === support.length;
  if (conflict) return { state: "conflict", quorum: support.length, required: QUORUM, proposal: null, verified: unique, rejected, conflicts: ranked.map(([group, members]) => ({ group, nodes: members.map((m) => m.observation.nodeId) })) };
  if (support.length < QUORUM) return { state: "awaiting_quorum", quorum: support.length, required: QUORUM, proposal: key.split(":")[1], signal: key.split(":")[0], verified: unique, rejected };
  return { state: "quorum_reached", quorum: support.length, required: QUORUM, proposal: key.split(":")[1], signal: key.split(":")[0], verified: unique, rejected };
};

export { FRESHNESS_MS, QUORUM, SCHEMA_VERSION };
