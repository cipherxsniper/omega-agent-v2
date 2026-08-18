import assert from "node:assert/strict";
import { coordinateSwarm, createNodeIdentity, createSignedObservation, verifyObservation } from "../src/lib/federatedSwarm.js";

const make = async (identity, proposal = "reconnect_sse") => createSignedObservation(identity, { missionId: "mission-test", signal: "transport", proposal, severity: "high" });
const a = await createNodeIdentity();
const b = await createNodeIdentity();
const one = await make(a);
const two = await make(b);
assert.equal((await verifyObservation(one)).valid, true);
assert.equal((await verifyObservation({ ...one, signature: one.signature.slice(0, -2) + "aa" })).valid, false);
assert.equal((await coordinateSwarm([one, two])).state, "quorum_reached");
assert.equal((await coordinateSwarm([one, one])).state, "awaiting_quorum");
const conflict = await make(b, "replay_last_checkpoint");
assert.equal((await coordinateSwarm([one, conflict])).state, "conflict");
const stale = { ...one, createdAt: new Date(Date.now() - 120_000).toISOString() };
assert.equal((await verifyObservation(stale)).reason, "stale_observation");
console.log("FEDERATED_SWARM_SMOKE_OK");
