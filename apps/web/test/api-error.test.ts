import { describe, expect, it } from 'vitest'
import { apiErrorCode } from '../app/utils/api-error'

describe('apiErrorCode', () => {
  it('passes known API error codes through', () => {
    expect(apiErrorCode({ detail: 'invalid_credentials' })).toBe('invalid_credentials')
    expect(apiErrorCode({ detail: 'email_taken' })).toBe('email_taken')
  })

  it('maps everything else, including validation errors, to unknown', () => {
    expect(apiErrorCode(undefined)).toBe('unknown')
    expect(apiErrorCode({ detail: [{ msg: 'too short' }] })).toBe('unknown')
    expect(apiErrorCode({ detail: 'something_new' })).toBe('unknown')
  })
})
