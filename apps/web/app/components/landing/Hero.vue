<script setup lang="ts">
const { t } = useI18n()

const facts = computed(() => [
  { label: t('hero.facts.numbersLabel'), value: t('hero.facts.numbersValue') },
  { label: t('hero.facts.decisionLabel'), value: t('hero.facts.decisionValue') },
  { label: t('hero.facts.opennessLabel'), value: t('hero.facts.opennessValue') }
])
</script>

<template>
  <section
    id="top"
    class="relative overflow-hidden"
  >
    <div class="container-page grid gap-12 pb-20 pt-16 sm:pt-24 lg:grid-cols-12 lg:gap-16">
      <div class="lg:col-span-7 xl:col-span-8">
        <p class="text-sm font-semibold uppercase tracking-wider text-primary">
          {{ t('hero.eyebrow') }}
        </p>

        <h1 class="mt-4 text-4xl font-semibold tracking-tight text-highlighted sm:text-6xl xl:text-7xl">
          {{ t('hero.title') }}
        </h1>

        <p class="mt-6 max-w-3xl text-lg leading-relaxed text-muted sm:text-xl">
          {{ t('hero.lead') }}
        </p>

        <div class="mt-9 flex flex-wrap items-center gap-3">
          <UButton
            to="#explore"
            size="lg"
            color="primary"
            trailing-icon="i-lucide-arrow-down"
            :label="t('hero.ctaPrimary')"
          />
          <UButton
            to="#about"
            size="lg"
            color="neutral"
            variant="outline"
            :label="t('hero.ctaSecondary')"
          />
        </div>
      </div>

      <dl class="grid content-center gap-6 lg:col-span-5 xl:col-span-4">
        <div
          v-for="fact in facts"
          :key="fact.label"
          class="rounded-xl border border-default bg-muted/40 px-6 py-5"
        >
          <dt class="text-sm text-muted">
            {{ fact.label }}
          </dt>
          <dd class="mt-1 text-lg font-medium text-highlighted">
            {{ fact.value }}
          </dd>
        </div>
      </dl>
    </div>
  </section>
</template>
