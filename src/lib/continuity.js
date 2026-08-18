const PREFIX = "omega_continuity_v1:";

const keyFor = (conversationId) => `${PREFIX}${conversationId}`;

export function readContinuityCheckpoint(conversationId) {
  if (!conversationId || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(keyFor(conversationId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function writeContinuityCheckpoint(conversationId, checkpoint) {
  if (!conversationId || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      keyFor(conversationId),
      JSON.stringify({
        version: 1,
        savedAt: new Date().toISOString(),
        ...checkpoint,
      }),
    );
  } catch {
    // Continuity is best-effort and must never block a conversation.
  }
}

export function clearContinuityCheckpoint(conversationId) {
  if (!conversationId || typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(keyFor(conversationId));
  } catch {
    // Ignore storage restrictions.
  }
}
