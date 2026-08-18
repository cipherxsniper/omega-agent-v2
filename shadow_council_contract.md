# Omega Shadow Council Contract

The Shadow Council is a pre-execution gate for consequential Omega actions. It has three roles: the **Planner** proposes an action and acceptance tests; the **Adversarial Critic** searches for unsafe scope, missing prerequisites, secret exposure, destructive side effects, ambiguous paths, and unsupported claims; and the **Verifier** checks the proposal against the actual workspace state, repository diff, capability registry, and required evidence. Only the primary ActionEngine can execute an approved action. The critic and verifier are read-only.

A proposal is executable only when all of the following are true: the requested capability is registered; every target path is normalized and allowed; the proposed diff has an expected hash or a deterministic source; the rollback plan exists for mutations; no secret-like material is staged; the acceptance tests are concrete; and the verifier returns `approved: true`. Any missing evidence produces a veto rather than a best-effort execution.

The critic has hard veto rules for unrestricted shell commands, device paths outside the approved root, credential or private-key material, destructive operations without rollback, network mutations without explicit confirmation, claimed success without an observable receipt, and model/tool choices that contradict the declared capability. It may also issue a soft warning, but soft warnings cannot silently become approvals.

Every council decision records a proposal hash, normalized target list, critic findings, verifier findings, approval state, veto reasons, acceptance tests, parent provenance identifier, and timestamp. The record is hash-chained and signed when AgentProof is configured. The council never receives or stores raw secrets, hidden chain-of-thought, or unrestricted device data. It reasons only over the action contract, observable metadata, and bounded diffs.

Creator attribution: Thomas Lee Harvey.
