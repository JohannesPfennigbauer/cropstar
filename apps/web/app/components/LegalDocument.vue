<script setup lang="ts">
import type { BlogLocale } from '#shared/blog'
import type { LegalDocument } from '#shared/legal'

const props = defineProps<{ document: LegalDocument }>()

const { t, locale } = useI18n()
const head = useLocaleHead()
const { formatDate } = useFigures()

const lang = computed(() => locale.value as BlogLocale)
// Both legal pages render this component; Nuxt may reuse the instance, so the key must follow the route.
const { data: page } = await useAsyncData(
  () => `legal-${lang.value}-${props.document}`,
  () => queryCollection(`legal_${lang.value}`).path(`/legal/${props.document}`).first()
)

if (!page.value) {
  throw createError({ statusCode: 404, statusMessage: 'Page not found', fatal: true })
}

useSeoMeta({
  title: () => `${page.value?.title} · Cropstar`,
  description: () => page.value?.description
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
    <main class="container-page py-12 sm:py-16">
      <article
        v-if="page"
        class="mx-auto max-w-3xl"
      >
        <h1 class="text-4xl font-semibold leading-tight text-highlighted sm:text-5xl">
          {{ page.title }}
        </h1>
        <p class="mt-4 text-sm text-dimmed">
          {{ t('legal.updated', { date: formatDate(page.updated) }) }}
        </p>
        <ContentRenderer
          :value="page"
          class="prose prose-cropstar mt-10 max-w-none"
        />
      </article>
    </main>
    <LandingFooter />
  </div>
</template>
