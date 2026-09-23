<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <section
    id="top"
    class="relative flex min-h-[42rem] overflow-hidden sm:min-h-[calc(100vh-9rem)]"
  >
    <img
      src="/images/landing/fields/sunrise-farmland.jpg"
      alt=""
      class="absolute inset-0 size-full object-cover object-center"
    >
    <div class="absolute inset-0 bg-[linear-gradient(90deg,rgba(52,55,47,.88)_0%,rgba(52,55,47,.62)_48%,rgba(82,103,73,.12)_82%)]" />

    <div class="container-page relative flex flex-1 items-end py-12 sm:py-14">
      <div class="max-w-4xl">
        <p class="text-sm font-semibold uppercase tracking-wider text-white/80">
          {{ t('hero.eyebrow') }}
        </p>

        <h1 class="mt-4 max-w-4xl text-5xl font-semibold leading-[1.05] text-white sm:text-6xl xl:text-7xl">
          <span>{{ t('hero.titleFirst') }}</span>
          <span class="block">{{ t('hero.titleSecond') }}</span>
        </h1>

        <p class="mt-6 max-w-2xl text-lg leading-relaxed text-white/85 sm:text-xl">
          {{ t('hero.lead') }}
        </p>

        <div class="mt-9 flex flex-wrap items-center gap-3">
          <UButton
            to="#explore"
            size="lg"
            color="primary"
            trailing-icon="i-lucide-arrow-down"
            :label="t('hero.ctaPrimary')"
            class="rounded-full"
          />
          <UButton
            to="#about"
            size="lg"
            color="neutral"
            variant="link"
            :label="t('hero.ctaSecondary')"
            class="text-white hover:text-white/80"
          />
        </div>
      </div>
    </div>
  </section>
</template>
