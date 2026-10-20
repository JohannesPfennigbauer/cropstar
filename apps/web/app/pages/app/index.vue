<script setup lang="ts">
definePageMeta({ layout: 'app' })

const { t } = useI18n()
const { farm } = useAuth()

useSeoMeta({ title: () => t('app.nav.home') })
</script>

<template>
  <div class="max-w-3xl">
    <h1 class="text-3xl font-semibold text-highlighted sm:text-4xl">
      {{ t('app.home.title', { farm: farm?.name ?? '' }) }}
    </h1>
    <p class="mt-3 text-lg text-muted">
      {{ t('app.home.lead') }}
    </p>
    <UAlert
      class="mt-8"
      color="neutral"
      variant="subtle"
      icon="i-lucide-sprout"
      :description="t('app.home.comingNext')"
    />
  </div>
</template>
