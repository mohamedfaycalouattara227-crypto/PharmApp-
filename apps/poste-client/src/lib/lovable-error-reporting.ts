/**
 * Minimal error reporter — no-op in production unless a hook is wired.
 * Kept as a stable module so components can import it without breaking builds.
 */
type Ctx = Record<string, unknown>;

export function reportLovableError(error: unknown, context: Ctx = {}): void {
  if (typeof window === "undefined") return;
  try {
    // eslint-disable-next-line no-console
    console.error("[error]", context, error);
  } catch {
    /* ignore */
  }
}
