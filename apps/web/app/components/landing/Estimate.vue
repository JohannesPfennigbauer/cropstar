<script setup lang="ts">
import type { Driver, Estimate } from '~/utils/illustrative-response'

const props = defineProps<{
  label: string
  estimate: Estimate
  unit: string
  domainMin: number
  domainMax: number
  note?: string
}>()

const { t } = useI18n()
const { format, withUnit } = useFigures()

function toPercent(value: number): number {
  const span = props.domainMax - props.domainMin
  if (span <= 0) return 0
  return Math.min(100, Math.max(0, ((value - props.domainMin) / span) * 100))
}

const bandLeft = computed(() => toPercent(props.estimate.low))
const bandWidth = computed(() =>
  Math.max(1.5, toPercent(props.estimate.high) - toPercent(props.estimate.low))
)
const markerLeft = computed(() => toPercent(props.estimate.value))

const bandText = computed(() =>
  `${format(props.estimate.low, props.estimate.precision)} – ${withUnit(props.estimate.high, props.estimate.precision, props.unit)}`
)

function driverDetail(driver: Driver): string {
  const reference = t(`explore.drivers.${driver.id}Reference`)
  if (driver.magnitude < 0.0005) {
    return t('explore.drivers.flat', { reference })
  }
  const delta = withUnit(driver.magnitude, props.estimate.precision, props.unit)
  return t(`explore.drivers.${driver.direction}`, { delta, reference })
}
</script>

<template>
  <div class="rounded-lg border border-default bg-default p-4">
    <div class="flex items-start justify-between gap-2">
      <p class="text-sm font-medium text-muted">
        {{ label }}
      </p>

      <UPopover :ui="{ content: 'w-80 p-4' }">
        <UButton
          size="xs"
          variant="ghost"
          color="neutral"
          icon="i-lucide-circle-help"
          :aria-label="t('explore.drivers.ariaWhy', { label })"
          :label="t('explore.drivers.why')"
        />

        <template #content>
          <p class="text-xs font-semibold uppercase tracking-wide text-dimmed">
            {{ t('explore.drivers.title') }}
          </p>
          <ul class="mt-3 space-y-3">
            <li
              v-for="driver in estimate.drivers"
              :key="driver.id"
            >
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-sm font-medium text-highlighted">
                  {{ t(`explore.drivers.${driver.id}`) }}
                </span>
                <span class="tabular text-xs text-dimmed">
                  {{ Math.round(driver.share * 100) }}%
                </span>
              </div>
              <div class="mt-1 h-1.5 w-full rounded-full bg-muted">
                <div
                  class="h-1.5 rounded-full bg-primary"
                  :style="{ width: `${driver.share * 100}%` }"
                />
              </div>
              <p class="mt-1 text-xs text-muted">
                {{ driverDetail(driver) }}
              </p>
            </li>
          </ul>
          <p class="mt-3 border-t border-default pt-3 text-xs text-dimmed">
            {{ t('explore.drivers.footnote') }}
          </p>
        </template>
      </UPopover>
    </div>

    <p class="mt-1 flex items-baseline gap-1.5">
      <span class="tabular text-3xl font-semibold text-highlighted">
        {{ format(estimate.value, estimate.precision) }}
      </span>
      <span
        v-if="unit"
        class="text-sm text-muted"
      >{{ unit }}</span>
    </p>

    <div
      class="relative mt-3 h-2 w-full rounded-full bg-elevated"
      role="img"
      :aria-label="t('explore.bandAria', {
        low: format(estimate.low, estimate.precision),
        high: withUnit(estimate.high, estimate.precision, unit)
      })"
    >
      <div
        class="absolute inset-y-0 rounded-full bg-primary/25 transition-all duration-200"
        :style="{ left: `${bandLeft}%`, width: `${bandWidth}%` }"
      />
      <div
        class="absolute -top-0.5 h-3 w-0.5 rounded-full bg-primary transition-all duration-200"
        :style="{ left: `${markerLeft}%` }"
      />
    </div>

    <p class="tabular mt-2 text-xs text-muted">
      {{ bandText }}
    </p>
    <p
      v-if="note"
      class="mt-1 text-xs text-dimmed"
    >
      {{ note }}
    </p>
  </div>
</template>
