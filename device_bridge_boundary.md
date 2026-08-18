# Omega Durable Device Bridge Boundary

The bridge is an explicit operator-authorized control channel for the Omega workspace, not unrestricted phone access. It must bind only to loopback on Termux and be exposed through an authenticated tunnel or private endpoint. Every request carries a short-lived bearer lease, a request identifier, and an idempotency key. The bridge must reject expired leases, malformed paths, traversal, symlinks that resolve outside approved roots, and commands outside the explicit capability registry.

The approved root is the Omega workspace. File operations are limited to an allowlist of repository-relative paths or explicitly approved path prefixes. The initial deployment scope includes the v2 backend source, tests, configuration templates, and service launcher files. Secrets, browser data, SSH material, Android private storage, shell history, personal files, and unrestricted filesystem enumeration are always denied.

Command execution is capability-based rather than arbitrary shell access. Initial capabilities are: read-only health and status; syntax checks for approved Python and JavaScript files; verified Git fetch and fast-forward; atomic application of an approved patch bundle; service restart through a named launcher; and end-to-end health, chat, SSE, and attachment probes. The bridge must not expose a general shell endpoint.

Each mutation creates a receipt containing request ID, actor label, approved capability, target paths, pre-change hashes, post-change hashes, timestamp, result status, and rollback reference. Mutations must be atomic or reversible. The lease expires automatically, the service fails closed when its token is missing or invalid, and a watchdog must not restart arbitrary processes—only the named Omega service.

The bridge is acceptable only when a read-only health request works remotely, the response exposes the scoped capability list, a denied-path test is rejected, a dry-run receipt is verifiable, and a single authorized patch can be applied and rolled back without touching any excluded path. Creator attribution for generated Omega work: Thomas Lee Harvey.
