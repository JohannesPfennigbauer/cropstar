<script setup lang="ts">
definePageMeta({ layout: 'app' })

const { t } = useI18n()
const localePath = useLocalePath()
const { farm } = useAuth()
const creating = ref(false)

useSeoMeta({ title: () => t('app.nav.home') })
</script>

<template>
  <div
    v-if="!farm"
    class="max-w-2xl"
  >
    <h1 class="text-3xl font-semibold text-highlighted sm:text-4xl">
      {{ t('app.farm.noneTitle') }}
    </h1>
    <p class="mt-3 text-lg text-muted">
      {{ t('app.farm.noneLead') }}
    </p>
    <UButton
      class="mt-6"
      icon="i-lucide-plus"
      :label="t('app.farm.createTitle')"
      @click="creating = true"
    />
    <AppCreateFarmDialog v-model:open="creating" />
  </div>
  <div
    v-else
    class="max-w-3xl"
  >
    <h1 class="text-3xl font-semibold text-highlighted sm:text-4xl">
      {{ t('app.home.title', { farm: farm?.name ?? '' }) }}
    </h1>
    <p class="mt-3 text-lg text-muted">
      {{ t('app.home.lead') }}
    </p>
    <UCard class="mt-8">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <p class="flex items-center gap-2 text-toned">
          <UIcon
            name="i-lucide-map"
            class="size-5 text-primary"
          />
          {{ t('app.home.plotsLead') }}
        </p>
        <UButton
          :to="localePath('/app/plots')"
          trailing-icon="i-lucide-arrow-right"
          :label="t('app.home.plotsCta')"
        />
      </div>
    </UCard>
  </div>
</template>
