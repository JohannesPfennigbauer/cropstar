<script setup lang="ts">
const { t } = useI18n()
const localePath = useLocalePath()
const { repositoryUrl } = useRuntimeConfig().public

const links = computed(() => [
  { label: t('nav.about'), to: { path: localePath('/'), hash: '#about' } },
  { label: t('nav.explore'), to: { path: localePath('/'), hash: '#explore' } },
  { label: t('nav.blog'), to: localePath('/blog') },
  { label: t('nav.contact'), to: { path: localePath('/'), hash: '#contact' } }
])
</script>

<template>
  <header class="sticky top-0 z-50 bg-default/90 backdrop-blur-md">
    <div class="container-page flex h-18 items-center justify-between gap-4">
      <NuxtLink
        :to="{ path: localePath('/'), hash: '#top' }"
      >
        <CropstarLogo />
      </NuxtLink>

      <nav class="hidden items-center gap-1 md:flex">
        <UButton
          v-for="link in links"
          :key="link.label"
          :to="link.to"
          color="neutral"
          variant="ghost"
          size="sm"
          :label="link.label"
          class="font-display rounded-full"
        />
      </nav>

      <div class="flex items-center gap-2">
        <LocaleSwitch />

        <UButton
          :to="localePath('/app')"
          color="primary"
          variant="solid"
          size="sm"
          icon="i-lucide-log-in"
          :label="t('nav.signIn')"
          class="font-display rounded-full"
        />

        <UButton
          :to="repositoryUrl"
          target="_blank"
          rel="noopener"
          color="neutral"
          variant="ghost"
          icon="i-lucide-github"
          :aria-label="t('nav.github')"
          class="hidden sm:inline-flex"
        />
      </div>
    </div>
  </header>
</template>
