<script setup lang="ts">
import {
  MANURE_INPUT,
  RAINFALL_INPUT,
  illustrativeOutcome
} from '~/utils/illustrative-response'

const { t } = useI18n()
const { withUnit } = useFigures()

const rainfall = ref(450)
const manure = ref(25)

const outcome = computed(() => illustrativeOutcome(rainfall.value, manure.value))

const seasons = computed(() => [
  { label: t('explore.seasons.dry'), mm: 220 },
  { label: t('explore.seasons.average'), mm: 480 },
  { label: t('explore.seasons.wet'), mm: 680 }
])

const diagnostics = computed(() => [
  {
    key: 'water',
    label: t('explore.diagnostics.waterStressLabel'),
    value: withUnit(outcome.value.waterStressDays, 0, t('units.days')),
    note: t('explore.diagnostics.waterStressNote')
  },
  {
    key: 'deficit',
    label: t('explore.diagnostics.nDeficitLabel'),
    value: withUnit(outcome.value.nDeficitDays, 0, t('units.days')),
    note: t('explore.diagnostics.nDeficitNote')
  },
  {
    key: 'export',
    label: t('explore.diagnostics.nExportLabel'),
    value: withUnit(outcome.value.nExportedInGrain, 0, t('units.kgN')),
    note: t('explore.diagnostics.nExportNote')
  },
  {
    key: 'remaining',
    label: t('explore.diagnostics.nRemainingLabel'),
    value: withUnit(outcome.value.nRemaining, 0, t('units.kgN')),
    note: outcome.value.nRemaining < 0
      ? t('explore.diagnostics.nRemainingNegative')
      : t('explore.diagnostics.nRemainingPositive')
  }
])
</script>

<template>
  <section
    id="explore"
    class="scroll-mt-20 border-y border-default bg-muted/40 py-20"
  >
    <div class="container-page">
      <div class="max-w-3xl">
        <p class="text-sm font-semibold uppercase tracking-wider text-primary">
          {{ t('explore.eyebrow') }}
        </p>
        <h2 class="mt-2 text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
          {{ t('explore.title') }}
        </h2>
        <p class="mt-4 text-lg text-muted">
          {{ t('explore.lead') }}
        </p>
      </div>

      <div class="mt-8 flex items-start gap-3 rounded-lg border border-warning/40 bg-warning/10 p-4">
        <UIcon
          name="i-lucide-triangle-alert"
          class="mt-0.5 size-5 shrink-0 text-warning"
        />
        <div>
          <p class="text-sm font-semibold text-highlighted">
            {{ t('explore.provenance.headline') }}
          </p>
          <p class="mt-1 max-w-4xl text-sm text-muted">
            {{ t('explore.provenance.detail') }}
          </p>
        </div>
      </div>

      <div class="mt-10 grid gap-6 lg:grid-cols-12">
        <div class="lg:col-span-4 xl:col-span-3">
          <div class="rounded-xl border border-default bg-default p-5">
            <div>
              <div class="flex items-baseline justify-between gap-2">
                <label
                  for="rainfall"
                  class="text-sm font-medium text-highlighted"
                >
                  {{ t('explore.inputs.rainfallLabel') }}
                </label>
                <span class="tabular text-sm text-muted">
                  {{ withUnit(rainfall, 0, t('units.mm')) }}
                </span>
              </div>
              <USlider
                id="rainfall"
                v-model="rainfall"
                class="mt-3"
                :min="RAINFALL_INPUT.min"
                :max="RAINFALL_INPUT.max"
                :step="RAINFALL_INPUT.step"
              />
              <div class="mt-3 flex flex-wrap gap-2">
                <UButton
                  v-for="season in seasons"
                  :key="season.label"
                  size="xs"
                  color="neutral"
                  :variant="rainfall === season.mm ? 'solid' : 'outline'"
                  :label="season.label"
                  @click="rainfall = season.mm"
                />
              </div>
              <p class="mt-3 text-xs text-dimmed">
                {{ t('explore.inputs.rainfallHelp') }}
              </p>
            </div>

            <div class="mt-8">
              <div class="flex items-baseline justify-between gap-2">
                <label
                  for="manure"
                  class="text-sm font-medium text-highlighted"
                >
                  {{ t('explore.inputs.manureLabel') }}
                </label>
                <span class="tabular text-sm text-muted">
                  {{ withUnit(manure, 0, t('units.tPerHa')) }}
                </span>
              </div>
              <USlider
                id="manure"
                v-model="manure"
                class="mt-3"
                :min="MANURE_INPUT.min"
                :max="MANURE_INPUT.max"
                :step="MANURE_INPUT.step"
              />

              <dl class="mt-4 space-y-2 rounded-lg bg-elevated/60 px-3 py-2.5">
                <div class="flex items-start justify-between gap-3">
                  <dt class="text-xs text-muted">
                    {{ t('explore.inputs.totalN') }}
                  </dt>
                  <dd class="tabular shrink-0 text-sm font-medium text-highlighted">
                    {{ withUnit(outcome.totalN, 0, t('units.kgN')) }}
                  </dd>
                </div>
                <div class="flex items-start justify-between gap-3">
                  <dt class="text-xs text-muted">
                    {{ t('explore.inputs.availableN') }}
                  </dt>
                  <dd class="tabular shrink-0 text-sm font-medium text-primary">
                    {{ withUnit(outcome.availableN, 0, t('units.kgN')) }}
                  </dd>
                </div>
              </dl>

              <p
                v-if="outcome.exceedsManureCeiling"
                class="mt-3 flex gap-2 text-xs text-muted"
              >
                <UIcon
                  name="i-lucide-scale"
                  class="mt-0.5 size-4 shrink-0 text-warning"
                />
                {{ t('explore.inputs.ceiling') }}
              </p>

              <p class="mt-3 text-xs text-dimmed">
                {{ t('explore.inputs.manureHelp') }}
              </p>
            </div>
          </div>
        </div>

        <div class="lg:col-span-4 xl:col-span-4">
          <div class="overflow-hidden rounded-xl border border-default bg-default">
            <LandingWheat :outcome="outcome" />
          </div>
          <p class="mt-3 text-xs leading-relaxed text-dimmed">
            {{ t('explore.caption') }}
          </p>
        </div>

        <div class="grid content-start gap-4 sm:grid-cols-2 lg:col-span-4 xl:col-span-5">
          <LandingEstimate
            :label="t('explore.outputs.yield')"
            :estimate="outcome.grainYield"
            :unit="t('units.tPerHa')"
            :domain-min="0"
            :domain-max="6"
          />
          <LandingEstimate
            :label="t('explore.outputs.protein')"
            :estimate="outcome.grainProtein"
            :unit="t('units.percent')"
            :domain-min="7"
            :domain-max="15"
          />
          <LandingEstimate
            :label="t('explore.outputs.cover')"
            :estimate="outcome.groundCover"
            unit=""
            :domain-min="0"
            :domain-max="1"
            :note="t('explore.outputs.coverNote')"
          />
          <LandingEstimate
            :label="t('explore.outputs.height')"
            :estimate="outcome.plantHeight"
            :unit="t('units.cm')"
            :domain-min="30"
            :domain-max="110"
          />
        </div>
      </div>

      <div class="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="item in diagnostics"
          :key="item.key"
          class="rounded-lg border border-default bg-default px-4 py-3"
        >
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-sm text-muted">{{ item.label }}</span>
            <span class="tabular text-sm font-semibold text-highlighted">
              {{ item.value }}
            </span>
          </div>
          <p class="mt-1 text-xs text-dimmed">
            {{ item.note }}
          </p>
        </div>
      </div>

      <p class="mt-8 max-w-4xl text-sm text-muted">
        {{ t('explore.closing') }}
      </p>
    </div>
  </section>
</template>
