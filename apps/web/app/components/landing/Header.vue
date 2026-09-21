<script setup lang="ts">
const { locale, locales, t } = useI18n()
const switchLocalePath = useSwitchLocalePath()
const { repositoryUrl } = useRuntimeConfig().public

const links = [
  { label: t('nav.about'), to: '#about' },
  { label: t('nav.explore'), to: '#explore' },
  { label: t('nav.contact'), to: '#contact' }
]

const available = computed(() =>
  (locales.value as Array<{ code: typeof locale.value, name?: string }>).map(entry => ({
    code: entry.code,
    name: entry.name ?? entry.code
  }))
)
</script>

<template>
  <header class="sticky top-0 z-50 border-b border-default bg-default/85 backdrop-blur">
    <div class="container-page flex h-16 items-center justify-between gap-4">
      <a
        href="#top"
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
        <span class="text-lg font-semibold tracking-tight text-highlighted">Cropstar</span>
      </a>

      <nav class="hidden items-center gap-1 md:flex">
        <UButton
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          color="neutral"
          variant="ghost"
          size="sm"
          :label="link.label"
        />
      </nav>

      <div class="flex items-center gap-2">
        <div
          class="flex items-center rounded-md border border-default p-0.5"
          :aria-label="t('language.label')"
        >
          <NuxtLink
            v-for="entry in available"
            :key="entry.code"
            :to="switchLocalePath(entry.code)"
            class="rounded px-2 py-1 text-xs font-medium uppercase transition-colors"
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
        <UButton
          to="#contact"
          color="primary"
          size="sm"
          :label="t('nav.earlyAccess')"
        />
      </div>
    </div>
  </header>
</template>
