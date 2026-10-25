import { fileURLToPath } from 'node:url'
import { defineCollection, defineContentConfig } from '@nuxt/content'
import { authorSchema, postSchema } from './shared/blog'
import { legalSchema } from './shared/legal'

// Authoring lives in the repo-level content/ folder, outside the app.
const cwd = fileURLToPath(new URL('../../content', import.meta.url))

function blogCollection(locale: string) {
  return defineCollection({
    type: 'page',
    source: { cwd, include: `blog/${locale}/*.md`, prefix: '/blog' },
    schema: postSchema
  })
}

function legalCollection(locale: string) {
  return defineCollection({
    type: 'page',
    source: { cwd, include: `legal/${locale}/*.md`, prefix: '/legal' },
    schema: legalSchema
  })
}

export default defineContentConfig({
  collections: {
    blog_de: blogCollection('de'),
    blog_en: blogCollection('en'),
    legal_de: legalCollection('de'),
    legal_en: legalCollection('en'),
    authors: defineCollection({
      type: 'data',
      source: { cwd, include: 'authors/*.yml' },
      schema: authorSchema
    })
  }
})
