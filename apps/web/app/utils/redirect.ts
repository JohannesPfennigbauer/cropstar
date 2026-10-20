/**
 * The in-app path to return to after signing in, or `fallback` when `target` could lead
 * anywhere else (absolute URLs, protocol-relative `//host`, backslash tricks).
 */
export function safeRedirect(target: unknown, fallback: string): string {
  if (typeof target !== 'string' || !target.startsWith('/')) return fallback
  if (target.startsWith('//') || target.includes('\\')) return fallback
  return /^\/(en\/)?app(\/|\?|$)/.test(target) ? target : fallback
}
