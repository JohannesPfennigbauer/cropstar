import { fileURLToPath } from 'node:url'
import { defineCollection, defineContentConfig } from '@nuxt/content'
import { authorSchema, postSchema } from './shared/blog'

// Authoring lives in the repo-level content/ folder, outside the app.
const cwd = fileURLToPath(new URL('../../content', import.meta.url))

function blogCollection(locale: string) {
  return defineCollection({
    type: 'page',
    source: { cwd, include: `blog/${locale}/*.md`, prefix: '/blog' },
    schema: postSchema
  })
}

export default defineContentConfig({
  collections: {
    blog_de: blogCollection('de'),
    blog_en: blogCollection('en'),
    authors: defineCollection({
      type: 'data',
      source: { cwd, include: 'authors/*.yml' },
      schema: authorSchema
    })
  }
})
