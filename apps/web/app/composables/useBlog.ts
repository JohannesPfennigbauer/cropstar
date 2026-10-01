import { BLOG_LOCALES, postSlug } from '#shared/blog'
import type { BlogLocale } from '#shared/blog'

export function blogCollection(locale: BlogLocale) {
  return `blog_${locale}` as const
}

/** Metadata of every published post in every locale; drafts only show in development. */
export async function fetchPostSummaries() {
  const lists = await Promise.all(BLOG_LOCALES.map(async (lang) => {
    const items = await queryCollection(blogCollection(lang))
      .select('path', 'title', 'description', 'date', 'updated', 'authors', 'topic', 'tags', 'cover', 'translationOf', 'translatedBy', 'draft')
      .all()
    return items.map(item => ({ ...item, lang }))
  }))
  return lists.flat()
    .filter(post => import.meta.dev || !post.draft)
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

export type PostSummary = Awaited<ReturnType<typeof fetchPostSummaries>>[number]

export async function fetchAuthors(ids: string[]) {
  const all = await queryCollection('authors').all()
  return ids.flatMap((id) => {
    const author = all.find(entry => postSlug(entry.stem) === id)
    return author ? [author] : []
  })
}
