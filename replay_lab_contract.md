# Omega Replay Laboratory Contract

A replay case is a JSON object containing only observable, redacted incident metadata: a stable case identifier, incident class, normalized input, expected outcome, observed outcome, provider/tool name, and optional repair proposal. Raw credentials, authorization headers, private keys, image bytes, cookies, and unrestricted device paths are never stored.

Replay is deterministic: the runner executes registered pure replay handlers against the normalized input and compares the result to the expected outcome. Unknown handlers fail closed. A replay cannot invoke a shell, network, device bridge, model provider, or arbitrary import.

A repair proposal is evaluated by the Shadow Council before it is recorded as accepted. The laboratory records a hash-chained receipt containing the case hash, result hash, council decision, and timestamp. Replay success means the observed failure is reproduced or the expected repaired outcome is reached; it never means a production deployment occurred.

Creator attribution: Thomas Lee Harvey.
