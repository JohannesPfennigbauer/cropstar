import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { basename, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parse } from 'yaml'
import { BLOG_LOCALES, authorSchema, postSchema, translationKey } from '../shared/blog'

// Nuxt Content does not validate frontmatter at build time, so this suite is the gate.
const root = fileURLToPath(new URL('../../../content', import.meta.url))

function frontmatter(file: string): unknown {
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(readFileSync(file, 'utf8'))
  if (!match) throw new Error(`${file}: missing frontmatter`)
  // YAML 1.1 turns unquoted dates into Date objects, like the content parser does.
  return parse(match[1]!, { version: '1.1' })
}

const authorIds = readdirSync(join(root, 'authors'))
  .filter(file => file.endsWith('.yml'))
  .map(file => basename(file, '.yml'))

const posts = BLOG_LOCALES.flatMap((lang) => {
  const dir = join(root, 'blog', lang)
  if (!existsSync(dir)) return []
  return readdirSync(dir)
    .filter(file => file.endsWith('.md'))
    .map(file => ({
      name: `blog/${lang}/${file}`,
      lang,
      slug: basename(file, '.md'),
      raw: frontmatter(join(dir, file))
    }))
})

describe('content/authors', () => {
  it.each(authorIds)('%s matches the author schema', (id) => {
    const raw = parse(readFileSync(join(root, 'authors', `${id}.yml`), 'utf8'))
    expect(authorSchema.strict().safeParse(raw).error?.issues ?? []).toEqual([])
  })
})

describe.each(posts)('content/$name', (post) => {
  const result = postSchema.strict().safeParse(post.raw)

  it('matches the post schema', () => {
    expect(result.error?.issues ?? []).toEqual([])
  })

  if (!result.success) return
  const data = result.data

  it('has a kebab-case file name', () => {
    expect(post.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)
  })

  it('references existing authors', () => {
    expect(data.authors.filter(id => !authorIds.includes(id))).toEqual([])
  })

  it('references an existing cover image', () => {
    if (data.cover) expect(existsSync(join(root, data.cover.src.slice(1)))).toBe(true)
  })

  it('only flags machine translations that name their original', () => {
    if (data.translatedBy) expect(data.translationOf).toBeDefined()
  })

  it('translates an original in another locale', () => {
    if (!data.translationOf) return
    const original = posts.find(other => other.slug === data.translationOf && other.lang !== post.lang)
    expect(original, `no post "${data.translationOf}" in another locale`).toBeDefined()
    expect((original!.raw as { translationOf?: string }).translationOf).toBeUndefined()
  })

  it('has at most one version per locale', () => {
    const key = translationKey({ path: post.slug, lang: post.lang, translationOf: data.translationOf })
    const sameLocale = posts.filter(other => other.lang === post.lang && translationKey({
      path: other.slug,
      lang: other.lang,
      translationOf: (other.raw as { translationOf?: string }).translationOf
    }) === key)
    expect(sameLocale.map(other => other.name)).toEqual([post.name])
  })
})
