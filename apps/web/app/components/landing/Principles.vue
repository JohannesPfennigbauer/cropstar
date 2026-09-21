<script setup lang="ts">
const { t } = useI18n()

const principles = computed(() => [
  { key: 'numbers', icon: 'i-lucide-sigma' },
  { key: 'scenarios', icon: 'i-lucide-columns-3' },
  { key: 'why', icon: 'i-lucide-git-branch' },
  { key: 'warnings', icon: 'i-lucide-message-square-warning' }
].map(item => ({
  ...item,
  title: t(`principles.${item.key}.title`),
  body: t(`principles.${item.key}.body`)
})))
</script>

<template>
  <section class="py-20">
    <div class="container-page">
      <div class="max-w-3xl">
        <h2 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
          {{ t('principles.title') }}
        </h2>
        <p class="mt-4 text-lg text-muted">
          {{ t('principles.lead') }}
        </p>
      </div>

      <div class="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="principle in principles"
          :key="principle.key"
          class="rounded-xl border border-default bg-default p-6"
        >
          <UIcon
            :name="principle.icon"
            class="size-6 text-primary"
          />
          <h3 class="mt-4 text-lg font-semibold text-highlighted">
            {{ principle.title }}
          </h3>
          <p class="mt-2 text-sm leading-relaxed text-muted">
            {{ principle.body }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
