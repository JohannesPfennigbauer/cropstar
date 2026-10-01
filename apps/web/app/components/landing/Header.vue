<script setup lang="ts">
const { locale, locales, t } = useI18n()
const switchLocalePath = useSwitchLocalePath()
const localePath = useLocalePath()
const { repositoryUrl } = useRuntimeConfig().public

const links = computed(() => [
  { label: t('nav.about'), to: { path: localePath('/'), hash: '#about' } },
  { label: t('nav.explore'), to: { path: localePath('/'), hash: '#explore' } },
  { label: t('nav.blog'), to: localePath('/blog') },
  { label: t('nav.contact'), to: { path: localePath('/'), hash: '#contact' } }
])

const available = computed(() =>
  (locales.value as Array<{ code: typeof locale.value, name?: string }>).map(entry => ({
    code: entry.code,
    name: entry.name ?? entry.code
  }))
)
</script>

<template>
  <header class="sticky top-0 z-50 bg-default/90 backdrop-blur-md">
    <div class="container-page flex h-18 items-center justify-between gap-4">
      <NuxtLink
        :to="{ path: localePath('/'), hash: '#top' }"
        class="flex items-center gap-2.5"
      >
        <svg
          viewBox="0 0 24 24"
          class="size-7 text-primary"
          aria-hidden="true"
        >
          <path
            d="M12 22V9"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            fill="none"
          />
          <path
            d="M12 9c0-2.5 1.4-4.6 3.4-5.6C15.4 6 14 8.2 12 9Zm0 0C12 6.5 10.6 4.4 8.6 3.4 8.6 6 10 8.2 12 9Zm0 4.6c0-2.3 1.3-4.2 3.1-5.1.1 2.4-1.2 4.4-3.1 5.1Zm0 0c0-2.3-1.3-4.2-3.1-5.1-.1 2.4 1.2 4.4 3.1 5.1Zm0 4.6c0-2.3 1.3-4.2 3.1-5.1.1 2.4-1.2 4.4-3.1 5.1Zm0 0c0-2.3-1.3-4.2-3.1-5.1-.1 2.4 1.2 4.4 3.1 5.1Z"
            fill="currentColor"
          />
        </svg>
        <span class="font-display text-xl font-semibold text-highlighted">Cropstar</span>
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
        <div
          class="flex items-center rounded-full border border-default p-0.5"
          :aria-label="t('language.label')"
        >
          <NuxtLink
            v-for="entry in available"
            :key="entry.code"
            :to="switchLocalePath(entry.code)"
            class="rounded-full px-2 py-1 text-xs font-medium uppercase transition-colors"
            :class="entry.code === locale
              ? 'bg-elevated text-highlighted'
              : 'text-muted hover:text-highlighted'"
          >
            {{ entry.code }}
          </NuxtLink>
        </div>

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
