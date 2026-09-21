<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <section
    id="about"
    class="scroll-mt-20 border-y border-default bg-muted/40 py-20"
  >
    <div class="container-page grid gap-10 lg:grid-cols-12 lg:gap-16">
      <div class="lg:col-span-5">
        <p class="text-sm font-semibold uppercase tracking-wider text-primary">
          {{ t('independence.eyebrow') }}
        </p>
        <h2 class="mt-2 text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl xl:text-5xl">
          {{ t('independence.title') }}
        </h2>
      </div>

      <div class="space-y-6 text-lg leading-relaxed text-muted lg:col-span-7">
        <p>{{ t('independence.p1') }}</p>
        <p>{{ t('independence.p2') }}</p>
        <p class="text-highlighted">
          {{ t('independence.p3') }}
        </p>
      </div>
    </div>
  </section>
</template>
