# Omega Federated Swarm Intelligence v1

Creator: Thomas Lee Harvey.

The swarm coordinator consumes signed, redacted observations from distinct Omega nodes. An observation contains a node ID, mission ID, dependency signal, proposed registered playbook, timestamp, schema version, public verification key, and signature. It never contains prompts, credentials, raw images, cookies, shell text, or unrestricted tool output.

A quorum is reached only when at least two distinct, freshly verified nodes independently support the same registered proposal. Reports older than 60 seconds, duplicate node IDs, invalid signatures, unknown schema versions, or malformed payloads are rejected. Conflicting proposals remain `conflict` until the Shadow Council or an operator resolves them. A single local node is shown as `awaiting_quorum`; it is not presented as a distributed consensus.

The browser integration exposes a real observation/verifier boundary and a DOM event adapter for authenticated peer transport. It does not pretend that browser tabs are remote agents. A production multi-device transport must deliver observations through an authenticated backend or bridge endpoint before they can count toward quorum.

Swarm decisions are read-only recommendations until the existing Self-Healing and Shadow Council gates approve a registered playbook. Every accepted, rejected, stale, conflicting, or quorum-pending observation is visible in the UI and may be written to the Mission Ledger as redacted metadata.
