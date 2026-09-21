<script setup lang="ts">
const { t } = useI18n()
const { contactEmail, repositoryUrl } = useRuntimeConfig().public

const mailto = computed(
  () => `mailto:${contactEmail}?subject=${encodeURIComponent(t('contact.subject'))}`
)

const status = computed(() =>
  (['now', 'next', 'then', 'later'] as const).map(key => ({
    key,
    icon: key === 'now' ? 'i-lucide-circle-check' : 'i-lucide-circle-dashed',
    title: t(`contact.status.${key}Title`),
    body: t(`contact.status.${key}Body`)
  }))
)
</script>

<template>
  <section
    id="contact"
    class="scroll-mt-20 border-t border-default py-20"
  >
    <div class="container-page grid gap-12 lg:grid-cols-12 lg:gap-16">
      <div class="lg:col-span-6">
        <h2 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
          {{ t('contact.title') }}
        </h2>
        <p class="mt-4 text-lg text-muted">
          {{ t('contact.lead') }}
        </p>
        <p class="mt-4 text-muted">
          {{ t('contact.body') }}
        </p>

        <div class="mt-8 flex flex-wrap gap-3">
          <UButton
            :to="mailto"
            size="lg"
            color="primary"
            icon="i-lucide-mail"
            :label="contactEmail"
          />
          <UButton
            :to="repositoryUrl"
            target="_blank"
            rel="noopener"
            size="lg"
            color="neutral"
            variant="outline"
            icon="i-lucide-github"
            :label="t('contact.codeButton')"
          />
        </div>

        <p class="mt-6 text-sm text-dimmed">
          {{ t('contact.privacy') }}
        </p>
      </div>

      <div class="rounded-xl border border-default bg-muted/40 p-6 lg:col-span-6">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-dimmed">
          {{ t('contact.statusTitle') }}
        </h3>
        <ul class="mt-5 space-y-5">
          <li
            v-for="step in status"
            :key="step.key"
            class="flex gap-3"
          >
            <UIcon
              :name="step.icon"
              class="mt-0.5 size-5 shrink-0"
              :class="step.key === 'now' ? 'text-primary' : 'text-dimmed'"
            />
            <div>
              <p class="font-medium text-highlighted">
                {{ step.title }}
              </p>
              <p class="text-sm text-muted">
                {{ step.body }}
              </p>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
