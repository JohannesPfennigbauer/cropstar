<script setup lang="ts">
import {
  PROVENANCE_REVISION,
  RAINFALL_INPUT,
  illustrativeOutcome
} from '~/utils/illustrative-response'

const props = withDefaults(defineProps<{
  manure?: number
  soilNitrogen?: number
}>(), {
  manure: 25,
  soilNitrogen: 25
})

const { t, locale } = useI18n()
const { withUnit } = useFigures()

const rainfall = ref(450)
const outcome = computed(() => illustrativeOutcome(rainfall.value, Number(props.manure), 'medium', Number(props.soilNitrogen)))
</script>

<template>
  <figure
    class="not-prose my-10 rounded-2xl border border-default bg-elevated/40 p-5"
    :lang="locale"
  >
    <div class="flex items-start gap-3">
      <UIcon
        name="i-lucide-info"
        class="mt-0.5 size-5 shrink-0 text-soil-500"
      />
      <div>
        <p class="text-sm font-semibold text-highlighted">
          {{ t('explore.provenance.headline') }}
        </p>
        <p class="mt-1 text-xs text-muted">
          {{ t('blog.illustration.inputs', {
            manure: withUnit(Number(manure), 0, t('units.tPerHa')),
            soilNitrogen: withUnit(Number(soilNitrogen), 0, t('units.kgN'))
          }) }}
          {{ t('blog.illustration.revision', { revision: PROVENANCE_REVISION }) }}
        </p>
      </div>
    </div>

    <div class="mt-5 grid gap-5 sm:grid-cols-2 sm:items-center">
      <div>
        <div class="flex items-baseline justify-between gap-2">
          <label
            for="illustrative-rainfall"
            class="text-sm font-medium text-highlighted"
          >
            {{ t('explore.inputs.rainfallLabel') }}
          </label>
          <span class="tabular text-sm text-muted">
            {{ withUnit(rainfall, 0, t('units.mm')) }}
          </span>
        </div>
        <USlider
          id="illustrative-rainfall"
          v-model="rainfall"
          class="mt-3"
          :min="RAINFALL_INPUT.min"
          :max="RAINFALL_INPUT.max"
          :step="RAINFALL_INPUT.step"
        />
      </div>

      <LandingEstimate
        :label="t('explore.outputs.yield')"
        :estimate="outcome.grainYield"
        :unit="t('units.tPerHa')"
        :domain-min="0"
        :domain-max="6"
      />
    </div>
  </figure>
</template>
