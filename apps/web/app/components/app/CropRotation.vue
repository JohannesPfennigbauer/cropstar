<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

/**
 * The crop rotation on this ground: this Harvest Year and the three before, oldest first,
 * each as a short crop label in its map colour. Earlier years come from the Plot's lineage.
 */
const props = defineProps<{ farmId: string, plot: Schemas['PlotProperties'] }>()

const { t } = useI18n()
const api = useApi()

const { data: lineage } = useAsyncData(
  () => `plot-lineage-${props.plot.id}`,
  async () => (await api.GET('/api/farms/{farm_id}/plots/{plot_id}/lineage', {
    params: { path: { farm_id: props.farmId, plot_id: props.plot.id } }
  })).data ?? [],
  { watch: [() => props.plot.id] }
)

interface Crop {
  key: string
  label: string
  background: string
  color: string
  title: string
}

function crop(year: number, p: { id: string, land_use_name: string, land_use_category: LandUseCategory, field_number: number, plot_number: number }, overlap: number | null): Crop {
  const background = landUseColor(p.land_use_category)
  const where = t('app.plots.rotationEntry', { year, crop: landUseLabel(p.land_use_name), field: p.field_number, plot: p.plot_number })
  return {
    key: p.id,
    label: landUseAbbreviation(p.land_use_name),
    background,
    color: textOnColor(background),
    title: overlap === null ? where : `${where} · ${t('app.plots.rotationOverlap', { overlap: Math.round(overlap * 100) })}`
  }
}

const years = computed(() => {
  const current = props.plot.harvest_year
  return [current - 3, current - 2, current - 1, current].map((year) => {
    const crops = year === current
      ? [crop(year, { ...props.plot, field_number: props.plot.field.number, plot_number: props.plot.number }, null)]
      : (lineage.value ?? []).filter(p => p.harvest_year === year).map(p => crop(year, p, p.overlap))
    return { year, crops }
  })
})
</script>

<template>
  <p
    class="flex flex-wrap items-center gap-1 text-xs text-muted"
    data-testid="crop-rotation"
  >
    <UIcon
      name="i-lucide-repeat"
      class="size-3.5 shrink-0"
    />
    <span class="mr-0.5">{{ t('app.plots.rotation') }}:</span>
    <template
      v-for="(entry, i) in years"
      :key="entry.year"
    >
      <UIcon
        v-if="i > 0"
        name="i-lucide-chevron-right"
        class="size-3 shrink-0 opacity-60"
        aria-hidden="true"
      />
      <span
        v-if="entry.crops.length"
        class="inline-flex gap-0.5"
      >
        <span
          v-for="c in entry.crops"
          :key="c.key"
          class="rounded px-1.5 py-0.5 font-semibold leading-none"
          :style="{ background: c.background, color: c.color }"
          :title="c.title"
          data-testid="crop-rotation-crop"
        >{{ c.label }}</span>
      </span>
      <span
        v-else
        class="rounded border border-dashed border-default px-1.5 py-0.5 leading-none"
        :title="t('app.plots.rotationUnknown', { year: entry.year })"
      >–</span>
    </template>
  </p>
</template>
