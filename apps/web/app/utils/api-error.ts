/** Error codes the API puts in `detail`; each has a translation under `app.errors`. */
const KNOWN_CODES = [
  'invalid_credentials',
  'email_taken',
  'registration_closed',
  'wrong_password',
  'invalid_or_expired_token',
  'email_not_configured',
  'not_signed_in'
] as const

export type ApiErrorCode = typeof KNOWN_CODES[number] | 'unknown'

export function apiErrorCode(error: unknown): ApiErrorCode {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  return (KNOWN_CODES as readonly unknown[]).includes(detail) ? detail as ApiErrorCode : 'unknown'
}
