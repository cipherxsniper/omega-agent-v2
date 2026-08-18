# Omega Mission Autopilot v1

Mission Autopilot converts an operator goal into a bounded sequence of measurable tasks. It is not an unrestricted autonomous agent. It may plan, inspect approved evidence, run registered capabilities, compare outcomes, and propose improvements. It may not silently expand scope, access unregistered devices, disclose secrets, or declare success without acceptance evidence.

Each mission has a stable identifier, creator attribution, objective, constraints, acceptance criteria, capability budget, current state, parent provenance, and an append-only event trail. The lifecycle is `proposed -> council_review -> ready -> executing -> blocked|completed|failed`. A mission may enter `blocked` when evidence is missing, a capability is unavailable, a council veto occurs, or a recovery budget is exhausted.

The planner decomposes the objective into atomic tasks. Each task names one registered capability, explicit inputs, expected evidence, retry budget, and rollback or non-mutation status. The observer compares actual receipts against acceptance criteria. The blind-spot detector flags goals with no measurable criterion, tasks with no evidence source, capabilities with no recent successful replay, and completed missions with unverified external effects.

The Shadow Council approves consequential tasks before execution. The Replay Laboratory supplies regression evidence for known failure classes. The Continuity Engine verifies repository/device identity before a mission is allowed to modify the agent. Self-improvement is proposal-only until the council approves it and isolated tests pass.

Creator attribution: Thomas Lee Harvey.
