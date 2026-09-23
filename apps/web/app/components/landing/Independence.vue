<script setup lang="ts">
const { t } = useI18n()

const principles = computed(() => [
  { key: 'openness', number: '01' },
  { key: 'numbers', number: '02' },
  { key: 'scenarios', number: '03' }
].map(item => ({
  ...item,
  title: t(`principles.${item.key}.title`),
  body: t(`principles.${item.key}.body`)
})))
</script>

<template>
  <section
    id="about"
    class="scroll-mt-20 overflow-hidden bg-muted/40 py-24 sm:py-32"
  >
    <div class="container-page">
      <div class="grid items-center gap-12 lg:grid-cols-12 lg:gap-16">
        <div class="lg:col-span-6 lg:col-start-2">
          <p class="text-sm font-semibold uppercase tracking-wider text-primary">
            {{ t('independence.eyebrow') }}
          </p>
          <h2 class="mt-3 text-4xl font-semibold leading-tight text-highlighted sm:text-5xl xl:text-6xl">
            {{ t('independence.title') }}
          </h2>
          <div class="mt-7 max-w-2xl space-y-5 text-lg leading-relaxed text-muted">
            <p>{{ t('independence.p1') }}</p>
            <p class="text-highlighted">
              {{ t('independence.p2') }}
            </p>
          </div>
        </div>

        <div class="relative mx-auto w-48 lg:col-span-3 lg:w-64">
          <div class="absolute inset-5 rounded-full bg-primary/10" />
          <img
            src="/images/landing/characters/green%20pea03.svg"
            alt=""
            class="relative w-full -rotate-3"
          >
        </div>
      </div>

      <div class="relative mt-24 sm:mt-32">
        <div class="max-w-2xl lg:ml-[9%]">
          <p class="text-sm font-semibold uppercase tracking-wider text-secondary">
            {{ t('principles.eyebrow') }}
          </p>
          <h3 class="mt-3 text-3xl font-semibold leading-tight text-highlighted sm:text-4xl">
            {{ t('principles.title') }}
          </h3>
          <p class="mt-4 text-lg text-muted">
            {{ t('principles.lead') }}
          </p>
        </div>

        <ol class="relative mt-14 grid gap-x-16 gap-y-10 md:grid-cols-2 lg:px-[9%]">
          <li
            v-for="principle in principles"
            :key="principle.key"
            class="border-t border-default pt-6 even:md:mt-16"
          >
            <div class="flex gap-5">
              <span class="font-display text-2xl font-semibold text-primary/60">
                {{ principle.number }}
              </span>
              <div>
                <h4 class="font-display text-xl font-semibold text-highlighted">
                  {{ principle.title }}
                </h4>
                <p class="mt-2 max-w-md leading-relaxed text-muted">
                  {{ principle.body }}
                </p>
              </div>
            </div>
          </li>
        </ol>

        <img
          src="/images/landing/characters/kidney%20bean02.svg"
          alt=""
          class="absolute -bottom-20 right-0 hidden w-24 rotate-6 lg:block xl:right-[2%] xl:w-28"
        >
      </div>
    </div>
  </section>
</template>
