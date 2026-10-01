<script setup lang="ts">
import { BLOG_LOCALES, postSlug, resolvePost, translationsOf } from '#shared/blog'
import type { BlogLocale } from '#shared/blog'

const route = useRoute()
const { t, locale } = useI18n()
const localePath = useLocalePath()
// Registers SEO settings; setI18nParams below then writes lang, hreflang and canonical with translated slugs.
useLocaleHead()
const setI18nParams = useSetI18nParams()
const { formatDate } = useFigures()
const { i18n: { baseUrl } } = useRuntimeConfig().public

const slug = String(route.params.slug)
const reader = locale.value as BlogLocale

const { data } = await useAsyncData(`blog-post-${reader}-${slug}`, async () => {
  const posts = await fetchPostSummaries()
  const summary = resolvePost(posts, slug, reader)
  if (!summary) return null
  const [page, authors] = await Promise.all([
    queryCollection(blogCollection(summary.lang)).path(summary.path).first(),
    fetchAuthors(summary.authors)
  ])
  return page ? { summary, page, authors, translations: translationsOf(posts, summary) } : null
})

if (!data.value) {
  throw createError({ statusCode: 404, statusMessage: 'Post not found', fatal: true })
}

const { summary, page, authors, translations } = data.value

// A typed-in slug from another locale should land on the reader's own translation.
const own = translations.find(post => post.lang === reader)
if (own && own.path !== summary.path) {
  await navigateTo(localePath(`/blog/${postSlug(own.path)}`), { redirectCode: 301 })
}

setI18nParams(Object.fromEntries(BLOG_LOCALES.map(lang => [
  lang,
  { slug: postSlug((translations.find(post => post.lang === lang) ?? summary).path) }
])))

const fallback = summary.lang !== reader
const original = summary.translatedBy === 'machine'
  ? translations.find(post => !post.translationOf)
  : undefined

function postLink(post: { path: string, lang: BlogLocale }): string {
  return localePath(`/blog/${postSlug(post.path)}`, post.lang)
}

useSeoMeta({
  title: `${page.title} · Cropstar`,
  description: page.description,
  ogTitle: page.title,
  ogDescription: page.description,
  ogType: 'article',
  ogImage: page.cover ? new URL(page.cover.src, baseUrl).href : undefined,
  articlePublishedTime: new Date(page.date).toISOString(),
  // Fallback pages duplicate the original; only the original should be indexed.
  robots: fallback ? 'noindex' : undefined
})
</script>

<template>
  <div class="min-h-screen bg-default text-default">
    <LandingHeader />
    <main class="container-page py-12 sm:py-16">
      <article
        class="mx-auto max-w-3xl"
        :lang="fallback ? summary.lang : undefined"
      >
        <UButton
          :to="localePath('/blog')"
          :label="t('blog.back')"
          icon="i-lucide-arrow-left"
          color="neutral"
          variant="ghost"
          size="sm"
          class="-ml-2"
          :lang="locale"
        />

        <div
          class="mt-6 flex flex-wrap items-center gap-2"
          :lang="locale"
        >
          <UBadge
            :label="t(`blog.topics.${page.topic}`)"
            color="primary"
            variant="soft"
          />
          <UBadge
            v-if="page.draft"
            :label="t('blog.draft')"
            color="warning"
            variant="soft"
          />
        </div>

        <h1 class="mt-4 text-4xl font-semibold leading-tight text-highlighted sm:text-5xl">
          {{ page.title }}
        </h1>
        <p class="mt-4 text-xl text-muted">
          {{ page.description }}
        </p>

        <p
          class="mt-6 text-sm text-dimmed"
          :lang="locale"
        >
          <span v-if="authors.length">
            {{ t('blog.byline', { authors: authors.map(author => author.name).join(', ') }) }} ·
          </span>
          <time :datetime="new Date(page.date).toISOString().slice(0, 10)">{{ formatDate(page.date) }}</time>
          <span v-if="page.updated">
            · {{ t('blog.updated', { date: formatDate(page.updated) }) }}
          </span>
        </p>

        <UAlert
          v-if="fallback"
          class="mt-8"
          color="neutral"
          variant="subtle"
          icon="i-lucide-languages"
          :title="t('blog.onlyIn', { language: t(`blog.languages.${summary.lang}`) })"
          :lang="locale"
        />
        <UAlert
          v-if="page.translatedBy === 'machine'"
          class="mt-8"
          color="neutral"
          variant="subtle"
          icon="i-lucide-bot"
          :title="t('blog.machineTranslated')"
          :actions="original
            ? [{ label: t('blog.readOriginal', { language: t(`blog.languages.${original.lang}`) }), to: postLink(original), color: 'neutral', variant: 'outline' }]
            : []"
          :lang="locale"
        />

        <img
          v-if="page.cover"
          :src="page.cover.src"
          :alt="page.cover.alt"
          class="mt-10 w-full rounded-2xl"
        >

        <ContentRenderer
          :value="page"
          class="prose prose-lg prose-cropstar mt-10 max-w-none"
        />

        <section
          v-if="page.sources?.length"
          class="mt-12 border-t border-default pt-6"
          :lang="locale"
        >
          <h2 class="text-xl font-semibold text-highlighted">
            {{ t('blog.sources') }}
          </h2>
          <ol class="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted">
            <li
              v-for="source in page.sources"
              :key="source.label"
            >
              <ULink
                v-if="source.url"
                :to="source.url"
                target="_blank"
                rel="noopener"
                class="text-toned underline underline-offset-2 hover:text-highlighted"
              >
                {{ source.label }}
              </ULink>
              <span v-else>{{ source.label }}</span>
            </li>
          </ol>
        </section>

        <section
          v-if="authors.some(author => author.bio?.[locale as BlogLocale])"
          class="mt-12 space-y-4 border-t border-default pt-6"
          :lang="locale"
        >
          <div
            v-for="author in authors.filter(entry => entry.bio?.[locale as BlogLocale])"
            :key="author.id"
          >
            <p class="font-display text-lg font-semibold text-highlighted">
              <ULink
                v-if="author.url"
                :to="author.url"
                target="_blank"
                rel="noopener"
              >
                {{ author.name }}
              </ULink>
              <span v-else>{{ author.name }}</span>
            </p>
            <p class="mt-1 text-sm text-muted">
              {{ author.bio?.[locale as BlogLocale] }}
            </p>
          </div>
        </section>
      </article>
    </main>
    <LandingFooter />
  </div>
</template>
