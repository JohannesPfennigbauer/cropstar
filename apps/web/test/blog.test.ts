import { describe, expect, it } from 'vitest'
import { pickForLocale, resolvePost, translationsOf } from '../shared/blog'
import type { PostRef } from '../shared/blog'

const willkommen: PostRef = { path: '/blog/willkommen', lang: 'de' }
const welcome: PostRef = { path: '/blog/welcome', lang: 'en', translationOf: 'willkommen' }
const deOnly: PostRef = { path: '/blog/bodenleben', lang: 'de' }
const enGuest: PostRef = { path: '/blog/soil-life', lang: 'en' }
const posts = [willkommen, welcome, deOnly, enGuest]

describe('pickForLocale', () => {
  it('prefers the reader locale and falls back to the original', () => {
    expect(pickForLocale(posts, 'en')).toEqual([welcome, deOnly, enGuest])
    expect(pickForLocale(posts, 'de')).toEqual([willkommen, deOnly, enGuest])
  })
})

describe('resolvePost', () => {
  it('finds a post in the reader locale', () => {
    expect(resolvePost(posts, 'welcome', 'en')).toBe(welcome)
  })

  it('falls back to another locale for an untranslated slug', () => {
    expect(resolvePost(posts, 'bodenleben', 'en')).toBe(deOnly)
  })

  it('returns undefined for an unknown slug', () => {
    expect(resolvePost(posts, 'missing', 'de')).toBeUndefined()
  })
})

describe('translationsOf', () => {
  it('groups a shared slug or translationOf', () => {
    expect(translationsOf(posts, welcome)).toEqual([willkommen, welcome])
    expect(translationsOf(posts, enGuest)).toEqual([enGuest])
  })
})
