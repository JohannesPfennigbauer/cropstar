<script setup lang="ts">
import {
  MANURE_INPUT,
  RAINFALL_INPUT,
  SOIL_N_INPUT,
  illustrativeOutcome
} from '~/utils/illustrative-response'
import type { DriverId, Estimate, SoilWaterStorage } from '~/utils/illustrative-response'

const { t } = useI18n()
const { withUnit } = useFigures()

const rainfall = ref(450)
const manure = ref(25)
const soilWaterStorage = ref<SoilWaterStorage>('medium')
const soilNitrogen = ref(25)

const outcome = computed(() => illustrativeOutcome(
  rainfall.value,
  manure.value,
  soilWaterStorage.value,
  soilNitrogen.value
))

const seasons = computed(() => [
  { label: t('explore.seasons.dry'), mm: 220 },
  { label: t('explore.seasons.average'), mm: 480 },
  { label: t('explore.seasons.wet'), mm: 680 }
])

const waterStorageOptions = computed(() => (
  ['low', 'medium', 'high'] as const
).map(value => ({
  value,
  label: t(`explore.inputs.waterStorage.${value}`)
})))

const outputs = computed(() => [
  {
    key: 'yield',
    label: t('explore.outputs.yield'),
    estimate: outcome.value.grainYield,
    unit: t('units.tPerHa'),
    domainMin: 0,
    domainMax: 6
  },
  {
    key: 'protein',
    label: t('explore.outputs.protein'),
    estimate: outcome.value.grainProtein,
    unit: t('units.percent'),
    domainMin: 7,
    domainMax: 15
  },
  {
    key: 'cover',
    label: t('explore.outputs.cover'),
    estimate: outcome.value.groundCover,
    unit: '',
    domainMin: 0,
    domainMax: 1,
    note: t('explore.outputs.coverNote')
  },
  {
    key: 'height',
    label: t('explore.outputs.height'),
    estimate: outcome.value.plantHeight,
    unit: t('units.cm'),
    domainMin: 30,
    domainMax: 110
  }
])

function driverShare(estimate: Estimate, driverId: DriverId): number {
  return estimate.drivers.find(driver => driver.id === driverId)?.share ?? 0
}

function setRainfall(value: number): void {
  rainfall.value = value
}

function setSoilWaterStorage(value: SoilWaterStorage): void {
  soilWaterStorage.value = value
}

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
    note: t('explore.diagnostics.nRemainingNote', {
      manure: withUnit(outcome.value.totalN, 0, t('units.kgN')),
      soil: withUnit(outcome.value.soilNitrogen, 0, t('units.kgN')),
      export: withUnit(outcome.value.nExportedInGrain, 0, t('units.kgN')),
      remaining: withUnit(outcome.value.nRemaining, 0, t('units.kgN'))
    })
  }
])
</script>

<template>
  <section
    id="explore"
    class="scroll-mt-20 bg-soil-800 py-24 text-paper sm:py-32"
  >
    <div class="container-page">
      <div class="max-w-4xl">
        <p class="text-sm font-semibold uppercase tracking-wider text-soil-200">
          {{ t('explore.eyebrow') }}
        </p>
        <h2 class="mt-3 text-4xl font-semibold leading-tight text-paper sm:text-5xl xl:text-6xl">
          {{ t('explore.title') }}
        </h2>
      </div>

      <div class="mt-8 flex max-w-5xl items-start gap-3 rounded-xl border border-paper/20 bg-paper/8 p-4">
        <UIcon
          name="i-lucide-info"
          class="mt-0.5 size-5 shrink-0 text-soil-200"
        />
        <div>
          <p class="text-sm font-semibold text-paper">
            {{ t('explore.provenance.headline') }}
          </p>
          <p class="mt-1 max-w-4xl text-sm text-paper/65">
            {{ t('explore.provenance.detail') }}
          </p>
        </div>
      </div>

      <div class="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.7fr)_minmax(0,1.1fr)] lg:items-start">
        <div class="rounded-2xl bg-paper p-4 text-charcoal shadow-xl shadow-charcoal/20">
          <div class="flex items-center justify-between gap-3">
            <h3 class="font-display text-xl font-semibold text-highlighted">
              {{ t('explore.inputs.title') }}
            </h3>

            <UPopover :ui="{ content: 'w-80 p-4' }">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                icon="i-lucide-circle-help"
                :aria-label="t('explore.inputs.help')"
                :label="t('explore.inputs.help')"
              />

              <template #content>
                <dl class="space-y-3">
                  <div>
                    <dt class="text-sm font-semibold text-highlighted">
                      {{ t('explore.inputs.rainfallLabel') }}
                    </dt>
                    <dd class="mt-1 text-xs text-muted">
                      {{ t('explore.inputs.rainfallHelp') }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-sm font-semibold text-highlighted">
                      {{ t('explore.inputs.waterStorageLabel') }}
                    </dt>
                    <dd class="mt-1 text-xs text-muted">
                      {{ t('explore.inputs.waterStorageHelp') }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-sm font-semibold text-highlighted">
                      {{ t('explore.inputs.soilNitrogenLabel') }}
                    </dt>
                    <dd class="mt-1 text-xs text-muted">
                      {{ t('explore.inputs.soilNitrogenHelp') }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-sm font-semibold text-highlighted">
                      {{ t('explore.inputs.manureLabel') }}
                    </dt>
                    <dd class="mt-1 text-xs text-muted">
                      {{ t('explore.inputs.manureHelp') }}
                    </dd>
                  </div>
                </dl>
              </template>
            </UPopover>
          </div>

          <p class="mt-4 text-xs font-bold uppercase text-primary">
            {{ t('explore.inputs.weatherSoilTitle') }}
          </p>

          <div>
            <div class="mt-2 flex items-baseline justify-between gap-2">
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
              class="mt-2"
              :min="RAINFALL_INPUT.min"
              :max="RAINFALL_INPUT.max"
              :step="RAINFALL_INPUT.step"
            />
            <div class="mt-2 flex flex-wrap gap-2">
              <UButton
                v-for="season in seasons"
                :key="season.label"
                size="xs"
                color="neutral"
                :variant="rainfall === season.mm ? 'solid' : 'outline'"
                :label="season.label"
                @click="setRainfall(season.mm)"
              />
            </div>
          </div>

          <fieldset class="mt-4 border-t border-default pt-3">
            <legend class="text-sm font-medium text-highlighted">
              {{ t('explore.inputs.waterStorageLabel') }}
            </legend>
            <div class="mt-2 grid grid-cols-3 gap-2">
              <UButton
                v-for="option in waterStorageOptions"
                :key="option.value"
                size="sm"
                color="primary"
                :variant="soilWaterStorage === option.value ? 'solid' : 'outline'"
                :label="option.label"
                class="justify-center rounded-full"
                @click="setSoilWaterStorage(option.value)"
              />
            </div>
          </fieldset>

          <p class="mt-4 border-t border-default pt-3 text-xs font-bold uppercase text-primary">
            {{ t('explore.inputs.nutrientsTitle') }}
          </p>

          <div class="mt-2">
            <div class="flex items-baseline justify-between gap-2">
              <label
                for="soil-nitrogen"
                class="text-sm font-medium text-highlighted"
              >
                {{ t('explore.inputs.soilNitrogenLabel') }}
              </label>
              <span class="tabular text-sm text-muted">
                {{ withUnit(soilNitrogen, 0, t('units.kgN')) }}
              </span>
            </div>
            <USlider
              id="soil-nitrogen"
              v-model="soilNitrogen"
              class="mt-2"
              :min="SOIL_N_INPUT.min"
              :max="SOIL_N_INPUT.max"
              :step="SOIL_N_INPUT.step"
            />
          </div>

          <div class="mt-4 border-t border-default pt-3">
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
              class="mt-2"
              :min="MANURE_INPUT.min"
              :max="MANURE_INPUT.max"
              :step="MANURE_INPUT.step"
            />

            <dl class="mt-3 space-y-1.5 rounded-lg bg-elevated/60 px-3 py-2">
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
                  {{ withUnit(outcome.availableManureN, 0, t('units.kgN')) }}
                </dd>
              </div>
              <div class="flex items-start justify-between gap-3 border-t border-default pt-2">
                <dt class="text-xs font-medium text-highlighted">
                  {{ t('explore.inputs.totalAvailableN') }}
                </dt>
                <dd class="tabular shrink-0 text-sm font-semibold text-highlighted">
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
          </div>
        </div>

        <div class="flex flex-col">
          <div class="aspect-[5/7] overflow-hidden rounded-2xl bg-paper shadow-xl shadow-charcoal/20">
            <LandingWheat :outcome="outcome" />
          </div>
          <p class="mt-3 text-xs leading-relaxed text-paper/55">
            {{ t('explore.caption') }}
          </p>
        </div>

        <div class="flex flex-col gap-2.5">
          <LandingEstimate
            v-for="output in outputs"
            :key="output.key"
            :label="output.label"
            :estimate="output.estimate"
            :unit="output.unit"
            :domain-min="output.domainMin"
            :domain-max="output.domainMax"
            :note="output.note"
            :show-why="false"
            compact
          />

          <UPopover :ui="{ content: 'w-[32rem] max-w-[calc(100vw-2rem)] p-5' }">
            <UButton
              block
              size="sm"
              variant="soft"
              color="neutral"
              icon="i-lucide-circle-help"
              :label="t('explore.drivers.why')"
              class="mt-1"
            />

            <template #content>
              <p class="font-display text-lg font-semibold text-highlighted">
                {{ t('explore.drivers.title') }}
              </p>
              <p class="mt-2 text-sm leading-relaxed text-muted">
                {{ t('explore.drivers.sharedIntro') }}
              </p>
              <ul class="mt-5 space-y-4">
                <li
                  v-for="output in outputs"
                  :key="output.key"
                >
                  <div class="flex items-center justify-between gap-3 text-xs">
                    <span class="font-semibold text-highlighted">{{ output.label }}</span>
                    <span class="tabular text-muted">
                      {{ Math.round(driverShare(output.estimate, 'water') * 100) }}%
                      {{ t('explore.drivers.waterShort') }} ·
                      {{ Math.round(driverShare(output.estimate, 'nitrogen') * 100) }}%
                      {{ t('explore.drivers.nitrogenShort') }}
                    </span>
                  </div>
                  <div class="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-elevated">
                    <span
                      class="bg-primary"
                      :style="{ width: `${driverShare(output.estimate, 'water') * 100}%` }"
                    />
                    <span
                      class="bg-secondary"
                      :style="{ width: `${driverShare(output.estimate, 'nitrogen') * 100}%` }"
                    />
                  </div>
                  <p class="mt-2 text-xs leading-relaxed text-muted">
                    {{ t(`explore.drivers.explanations.${output.key}`) }}
                  </p>
                </li>
              </ul>
              <p class="mt-5 border-t border-default pt-3 text-xs leading-relaxed text-dimmed">
                {{ t('explore.drivers.footnote') }}
              </p>
            </template>
          </UPopover>
        </div>
      </div>

      <div class="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="item in diagnostics"
          :key="item.key"
          class="rounded-xl border border-paper/15 bg-paper/8 px-4 py-3"
        >
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-sm text-paper/70">{{ item.label }}</span>
            <span class="tabular text-sm font-semibold text-paper">
              {{ item.value }}
            </span>
          </div>
          <p class="mt-1 text-xs text-paper/50">
            {{ item.note }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
