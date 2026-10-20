<script setup lang="ts">
const { locale, locales, t } = useI18n()
const switchLocalePath = useSwitchLocalePath()

const available = computed(() =>
  (locales.value as Array<{ code: typeof locale.value, name?: string }>).map(entry => ({
    code: entry.code,
    name: entry.name ?? entry.code
  }))
)
</script>

<template>
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
</template>
