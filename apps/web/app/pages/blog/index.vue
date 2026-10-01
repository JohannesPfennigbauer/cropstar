<script setup lang="ts">
import { pickForLocale, postSlug } from '#shared/blog'
import type { BlogLocale } from '#shared/blog'

const { t, locale } = useI18n()
const localePath = useLocalePath()
const head = useLocaleHead()

const { data: posts } = await useAsyncData('blog-posts', fetchPostSummaries)

const visible = computed(() => pickForLocale(posts.value ?? [], locale.value as BlogLocale))

useSeoMeta({
  title: () => t('blog.seo.title'),
  description: () => t('blog.seo.description'),
  ogTitle: () => t('blog.seo.title'),
  ogDescription: () => t('blog.seo.description'),
  ogType: 'website'
})

useHead(() => ({
  htmlAttrs: head.value.htmlAttrs,
  link: head.value.link,
  meta: head.value.meta
}))
</script>

<template>
  <div class="min-h-screen bg-default text-default">
    <LandingHeader />
    <main class="container-page py-16 sm:py-24">
      <div class="max-w-3xl">
        <p class="text-sm font-semibold uppercase tracking-wider text-primary">
          {{ t('blog.eyebrow') }}
        </p>
        <h1 class="mt-3 text-4xl font-semibold leading-tight text-highlighted sm:text-5xl">
          {{ t('blog.title') }}
        </h1>
        <p class="mt-4 text-lg text-muted">
          {{ t('blog.lead') }}
        </p>
      </div>

      <ul
        v-if="visible.length"
        class="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-3"
      >
        <li
          v-for="post in visible"
          :key="post.path"
        >
          <BlogCard
            :post="post"
            :to="localePath(`/blog/${postSlug(post.path)}`)"
          />
        </li>
      </ul>

      <p
        v-else
        class="mt-12 rounded-xl border border-dashed border-default p-8 text-muted"
      >
        {{ t('blog.empty') }}
      </p>
    </main>
    <LandingFooter />
  </div>
</template>
