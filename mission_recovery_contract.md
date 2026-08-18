# Omega Mission Replay & Recovery v1

Creator: Thomas Lee Harvey.

Replay & Recovery is a bounded, operator-visible recovery path for missions that stall, lose transport, fail a task, or finish without required evidence. It never silently replays a mutation. A replay may resume only from the last checkpoint whose receipt hash and mission proof ID are present in the local session state.

Recovery states are `healthy`, `degraded`, `checkpointed`, `replay_pending`, `replaying`, `recovered`, `blocked`, and `exhausted`. A recovery attempt has a maximum of two retries per mission, a stable replay ID, the failed event index, the last verified event hash, and a reason. The UI must show all of these fields.

The frontend may request a replay of the last bounded prompt through the existing backend job endpoint. It may not alter device files, bypass the Shadow Council, or claim that a replay repaired a mission until a new terminal SSE event is observed. If the stream fails again, recovery becomes `exhausted` and the mission remains available for manual retry.

Only approved, non-secret checkpoint data is persisted: mission ID, proof ID, objective summary, mode, last observed step, event count, and transcript hash. Raw credentials, image data, full prompts, and arbitrary tool output are excluded.
