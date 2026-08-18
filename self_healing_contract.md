# Omega Autonomous Mission Self-Healing v1

Creator: Thomas Lee Harvey.

Self-healing observes mission evidence and may propose a bounded recovery playbook when a dependency becomes degraded. It never executes arbitrary commands, shell text, network destinations, or unregistered tools. Every playbook is a named, versioned capability with a fixed input schema, fixed side-effect class, maximum duration, and rollback or stop condition.

Dependency signals include missing terminal SSE evidence, repeated transport errors, failed evidence validation, Shadow Council veto, provider fallback exhaustion, stale checkpoint age, and broken ledger integrity. A signal must be observed at least once and may be escalated only when its confidence and age thresholds are met.

Recovery states are `healthy`, `degraded`, `review_pending`, `approved`, `recovering`, `recovered`, `cooldown`, `blocked`, and `exhausted`. Each mission has a maximum of two automatic recovery attempts and a cooldown of 30 seconds between attempts. A veto, ledger-integrity failure, missing rollback boundary, or unknown playbook immediately blocks recovery.

Default v1 playbooks are safe and bounded: `reconnect_sse` (reopen the existing job stream), `replay_last_checkpoint` (re-submit the last approved mission text through the existing bounded replay path), and `refresh_ledger` (re-read and verify local ledger state). No playbook may alter device files or deployment configuration.

Every detection, council decision, playbook start, playbook result, cooldown, block, and exhaustion event must be visible in the Mission Autopilot UI and append-only Mission Ledger. Self-healing may improve continuity, but it may not claim external-world repair; it may only report that the observed mission transport or evidence path recovered.
