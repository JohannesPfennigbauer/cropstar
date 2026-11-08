<script setup lang="ts">
import type { PlotFilter, PlotGroup } from '~/utils/plot-filter'

/** Filter pills over the Plot list: groups in the first row, the crops of the chosen group in the second. */
const props = defineProps<{ plots: { land_use_name: string, land_use_category: LandUseCategory }[] }>()
const filter = defineModel<PlotFilter>({ required: true })

const { t } = useI18n()

const groups = computed(() => groupPills(props.plots))
const crops = computed(() => cropPills(props.plots, filter.value.group))

function groupLabel(group: PlotGroup): string {
  return group === 'active' ? t('app.plots.filter.active') : t(`app.landUseCategory.${group}`)
}

function toggleGroup(group: PlotGroup) {
  const next = filter.value.group === group ? null : group
  // Crops outside the new group would silently hide everything.
  const inside = new Set(cropPills(props.plots, next).map(c => c.name))
  filter.value = { group: next, crops: filter.value.crops.filter(c => inside.has(c)) }
}

// One scrollable line per row; a plain mouse wheel scrolls it sideways while it can move.
function sideways(event: WheelEvent) {
  const row = event.currentTarget as HTMLElement
  if (Math.abs(event.deltaX) > Math.abs(event.deltaY) || row.scrollWidth <= row.clientWidth) return
  const before = row.scrollLeft
  row.scrollLeft += event.deltaY
  if (row.scrollLeft !== before) event.preventDefault()
}

function toggleCrop(name: string) {
  const crops = filter.value.crops.includes(name)
    ? filter.value.crops.filter(c => c !== name)
    : [...filter.value.crops, name]
  filter.value = { ...filter.value, crops }
}
</script>

<template>
  <div
    class="min-w-0 space-y-1.5"
    data-testid="plot-filter-pills"
  >
    <div
      class="pill-row flex gap-1.5"
      role="group"
      :aria-label="t('app.plots.filter.groups')"
      @wheel="sideways"
    >
      <button
        v-for="pill in groups"
        :key="pill.group"
        type="button"
        class="pill"
        :class="{ on: filter.group === pill.group }"
        :aria-pressed="filter.group === pill.group"
        data-testid="plot-group-pill"
        @click="toggleGroup(pill.group)"
      >
        <span
          v-if="pill.group !== 'active'"
          class="size-2.5 shrink-0 rounded-sm"
          :style="{ backgroundColor: landUseColor(pill.group) }"
          aria-hidden="true"
        />
        {{ groupLabel(pill.group) }}
        <span class="count">{{ pill.count }}</span>
      </button>
    </div>
    <div
      v-if="crops.length > 1"
      class="pill-row flex gap-1"
      role="group"
      :aria-label="t('app.plots.filter.crops')"
      @wheel="sideways"
    >
      <button
        v-for="crop in crops"
        :key="crop.name"
        type="button"
        class="pill small"
        :class="{ on: filter.crops.includes(crop.name) }"
        :aria-pressed="filter.crops.includes(crop.name)"
        data-testid="plot-crop-pill"
        @click="toggleCrop(crop.name)"
      >
        <span
          class="size-2 shrink-0 rounded-sm"
          :style="{ backgroundColor: landUseColor(crop.category) }"
          aria-hidden="true"
        />
        {{ landUseLabel(crop.name) }}
        <span class="count">{{ crop.count }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.pill-row {
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: thin;
  padding-bottom: 0.25rem;
}
.pill {
  flex-shrink: 0;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  border: 1px solid var(--ui-border);
  padding: 0.125rem 0.625rem;
  font-size: 0.75rem;
  line-height: 1.25rem;
  color: var(--ui-text-toned);
  background: var(--ui-bg);
  transition: background-color 120ms, border-color 120ms;
}
.pill:hover {
  background: var(--ui-bg-elevated);
}
.pill.on {
  border-color: var(--ui-primary);
  background: color-mix(in srgb, var(--ui-primary) 14%, var(--ui-bg));
  color: var(--ui-text-highlighted);
  font-weight: 600;
}
.pill.small {
  padding: 0 0.5rem;
  font-size: 0.6875rem;
}
.count {
  font-variant-numeric: tabular-nums;
  color: var(--ui-text-muted);
}
</style>
