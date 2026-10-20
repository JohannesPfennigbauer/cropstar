<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

defineProps<{ task: Pick<Schemas['TaskOut'], 'fields' | 'plots'> }>()

const { t } = useI18n()
</script>

<template>
  <span
    v-for="field in task.fields"
    :key="field.id"
    class="inline-flex items-center gap-1"
  >
    <UIcon
      name="i-lucide-square-dashed"
      class="size-3.5"
    />
    {{ t('app.plots.field', { number: field.number }) }}<template v-if="field.name">
      · {{ field.name }}
    </template>
  </span>
  <span
    v-for="plot in task.plots"
    :key="plot.id"
    class="inline-flex items-center gap-1"
  >
    <span
      class="size-2.5 rounded-sm"
      :style="{ backgroundColor: landUseColor(plot.land_use_category) }"
      aria-hidden="true"
    />
    {{ t('app.tasks.plotRef', { field: plot.field_number, plot: plot.number }) }} · {{ landUseLabel(plot.land_use_name) }}
  </span>
</template>
