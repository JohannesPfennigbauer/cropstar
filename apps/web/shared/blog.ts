import { z } from 'zod'

export const BLOG_LOCALES = ['de', 'en'] as const
export type BlogLocale = typeof BLOG_LOCALES[number]

// Adding a topic: extend this list and add `blog.topics.<id>` to every locale file.
export const BLOG_TOPICS = ['practice', 'modeling'] as const
export type BlogTopic = typeof BLOG_TOPICS[number]

const slug = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'lowercase kebab-case')

// Files under content/media are served from /media.
const mediaPath = z.string().regex(/^\/media\/\S+$/, 'must start with /media/')

export const postSchema = z.object({
  title: z.string().min(1),
  description: z.string().min(1),
  date: z.date(),
  updated: z.date().optional(),
  authors: z.array(slug).min(1),
  topic: z.enum(BLOG_TOPICS),
  tags: z.array(slug).default([]),
  cover: z.object({
    src: mediaPath,
    alt: z.string().min(1)
  }).optional(),
  translationOf: slug.optional(),
  translatedBy: z.enum(['machine']).optional(),
  draft: z.boolean().default(false),
  sources: z.array(z.object({
    label: z.string().min(1),
    url: z.string().url().optional()
  })).default([])
})

export const authorSchema = z.object({
  name: z.string().min(1),
  url: z.string().url().optional(),
  bio: z.object({
    de: z.string().min(1),
    en: z.string().min(1)
  }).partial().optional()
})

export interface PostRef {
  path: string
  lang: BlogLocale
  translationOf?: string | null
}

export function postSlug(path: string): string {
  return path.split('/').pop() ?? ''
}

/** Posts sharing a key are translations of each other: a shared slug, or `translationOf` the original's slug. */
export function translationKey(post: PostRef): string {
  return post.translationOf || postSlug(post.path)
}

/** One entry per translation group, preferring the reader's locale, then the original. */
export function pickForLocale<T extends PostRef>(posts: T[], locale: BlogLocale): T[] {
  const groups = new Map<string, T[]>()
  for (const post of posts) {
    const key = translationKey(post)
    groups.set(key, [...(groups.get(key) ?? []), post])
  }
  return [...groups.values()].map(group =>
    group.find(post => post.lang === locale)
    ?? group.find(post => !post.translationOf)
    ?? group[0]!
  )
}

/** Resolves a slug for the reader's locale, falling back to a post with that slug in another locale. */
export function resolvePost<T extends PostRef>(posts: T[], slug: string, locale: BlogLocale): T | undefined {
  const matches = posts.filter(post => postSlug(post.path) === slug)
  return matches.find(post => post.lang === locale) ?? matches[0]
}

export function translationsOf<T extends PostRef>(posts: T[], post: T): T[] {
  const key = translationKey(post)
  return posts.filter(other => translationKey(other) === key)
}
