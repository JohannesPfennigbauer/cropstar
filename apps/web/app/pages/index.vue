<script setup lang="ts">
const { t } = useI18n()
const head = useLocaleHead()

useSeoMeta({
  title: () => t('seo.title'),
  description: () => t('seo.description'),
  ogTitle: () => t('seo.ogTitle'),
  ogDescription: () => t('seo.ogDescription'),
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
    <main>
      <LandingHero />
      <LandingIndependence />
      <LandingPrinciples />
      <LandingExplore />
      <LandingContact />
    </main>
    <LandingFooter />
  </div>
</template>
