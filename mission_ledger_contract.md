# Omega Mission Ledger v1

Creator: Thomas Lee Harvey.

The Mission Ledger is a local, append-only journal of observable mission state. It stores mission identifiers, proof identifiers, objective hashes, bounded task summaries, event types, event timestamps, receipt hashes, recovery status, and redacted evidence references. It never stores API keys, cookies, bearer tokens, image data, full prompts, raw assistant reasoning, or arbitrary tool output.

Each event is canonicalized as sorted JSON and chained to the previous event hash. The ledger head is the latest receipt hash. On hydration, the client verifies every event hash and rejects a ledger with a broken chain, unknown schema version, or invalid event shape. Invalid local data is quarantined rather than silently trusted.

Retention is bounded to the latest 50 missions and 500 events. Mission summaries remain reloadable; raw live transcripts are reduced to event metadata and evidence hashes. The ledger is local to the browser session profile and is not uploaded by this component. Cross-device synchronization is a future explicit feature requiring authentication and operator consent.

The ledger is evidence, not authority. A verified ledger record means the browser observed a terminal stream or continuity receipt; it does not independently certify the external world. The UI must distinguish `observed`, `verified`, `recovered`, `blocked`, and `corrupt` states.
