<script setup lang="ts">
const { t } = useI18n()
const { contactEmail, repositoryUrl } = useRuntimeConfig().public

const mailto = computed(
  () => `mailto:${contactEmail}?subject=${encodeURIComponent(t('contact.subject'))}`
)

const status = computed(() =>
  (['now', 'next', 'then', 'later'] as const).map((key, index) => ({
    key,
    number: String(index + 1).padStart(2, '0'),
    title: t(`contact.status.${key}Title`),
    body: t(`contact.status.${key}Body`)
  }))
)
</script>

<template>
  <section
    id="contact"
    class="scroll-mt-20"
  >
    <div class="bg-paper py-20 sm:py-24">
      <div class="container-page grid items-center gap-12 lg:grid-cols-12 lg:gap-16">
        <div class="lg:col-span-5">
          <p class="text-sm font-bold uppercase text-soil-700">
            {{ t('contact.eyebrow') }}
          </p>
          <h2 class="mt-4 text-4xl font-semibold text-highlighted sm:text-5xl">
            {{ t('contact.titleLine1') }}<br>
            {{ t('contact.titleLine2') }}
          </h2>
          <p class="mt-6 text-lg leading-relaxed text-muted">
            {{ t('contact.lead') }}
          </p>
          <p class="mt-4 leading-relaxed text-muted">
            {{ t('contact.body') }}
          </p>

          <div class="mt-8 flex flex-wrap gap-3">
            <UButton
              :to="mailto"
              size="lg"
              color="primary"
              icon="i-lucide-mail"
              :label="t('contact.contactButton')"
            />
            <UButton
              :to="repositoryUrl"
              target="_blank"
              rel="noopener"
              size="lg"
              color="neutral"
              variant="solid"
              icon="i-lucide-github"
              :label="t('contact.codeButton')"
            />
          </div>

          <p class="mt-5 text-sm text-dimmed">
            {{ t('contact.privacy') }}
          </p>
        </div>

        <div class="rounded-xl bg-leaf-300 p-6 shadow-xl shadow-charcoal/10 sm:p-8 lg:col-span-7">
          <p class="text-sm font-bold uppercase text-leaf-800">
            {{ t('contact.roadmapEyebrow') }}
          </p>
          <h3 class="mt-2 text-3xl font-semibold text-charcoal">
            {{ t('contact.statusTitle') }}
          </h3>

          <ol class="relative mt-7 space-y-6 before:absolute before:bottom-5 before:left-5 before:top-5 before:w-px before:bg-leaf-700/25">
            <li
              v-for="step in status"
              :key="step.key"
              class="relative flex gap-4"
            >
              <span class="relative z-10 flex size-10 shrink-0 items-center justify-center rounded-full bg-leaf-700 font-display text-sm font-semibold text-paper ring-4 ring-leaf-300">
                {{ step.number }}
              </span>
              <div class="pt-1">
                <h4 class="text-lg font-semibold text-charcoal">
                  {{ step.title }}
                </h4>
                <p class="mt-1 text-sm leading-relaxed text-leaf-900/80">
                  {{ step.body }}
                </p>
              </div>
            </li>
          </ol>
        </div>
      </div>
    </div>
  </section>
</template>
