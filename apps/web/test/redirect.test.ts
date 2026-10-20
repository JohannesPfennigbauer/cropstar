import { describe, expect, it } from 'vitest'
import { safeRedirect } from '../app/utils/redirect'

describe('safeRedirect', () => {
  it('keeps paths inside the farm app', () => {
    expect(safeRedirect('/app', '/x')).toBe('/app')
    expect(safeRedirect('/app/account?tab=1', '/x')).toBe('/app/account?tab=1')
    expect(safeRedirect('/en/app/account', '/x')).toBe('/en/app/account')
  })

  it('falls back for anything that could leave the app', () => {
    for (const target of [
      undefined,
      ['/app'],
      'https://evil.example/app',
      '//evil.example/app',
      '/\\evil.example',
      'app',
      '/blog',
      '/apple'
    ]) {
      expect(safeRedirect(target, '/app')).toBe('/app')
    }
  })
})
