<script setup lang="ts">
definePageMeta({ layout: 'app' })

const { t } = useI18n()
const api = useApi()
const localePath = useLocalePath()
const { farm } = useAuth()
const { selected: harvestYear, years } = useHarvestYear()
const { hectares } = useFormat()

useSeoMeta({ title: () => t('app.plots.title') })

const { data, status } = await useAsyncData('plots', async () => {
  if (!farm.value || harvestYear.value === null) return null
  const path = { farm_id: farm.value.id }
  const query = { harvest_year: harvestYear.value }
  const [plots, fields] = await Promise.all([
    api.GET('/api/farms/{farm_id}/plots', { params: { path, query } }),
    api.GET('/api/farms/{farm_id}/fields', { params: { path, query } })
  ])
  if (!plots.data || !fields.data) throw createError({ statusCode: 500 })
  return { plots: plots.data, fields: fields.data }
}, { watch: [harvestYear, () => farm.value?.id] })

const hovered = ref<string | null>(null)

const groups = computed(() => {
  if (!data.value) return []
  return data.value.fields.features.map(field => ({
    field: field.properties,
    plots: data.value!.plots.features
      .filter(plot => plot.properties.field.id === field.id)
      .map(plot => plot.properties)
  }))
})

function openPlot(id: string) {
  return navigateTo(localePath(`/app/plots/${id}`))
}
</script>

<template>
  <div
    v-if="years.length === 0 && status !== 'pending'"
    class="max-w-2xl"
  >
    <h1 class="text-3xl font-semibold text-highlighted">
      {{ t('app.plots.title') }}
    </h1>
    <UAlert
      class="mt-6"
      color="neutral"
      variant="subtle"
      icon="i-lucide-map"
      :title="t('app.plots.emptyTitle')"
      :description="t('app.plots.empty')"
    />
  </div>

  <div
    v-else
    class="grid gap-6 lg:h-[calc(100dvh-9rem)] lg:grid-cols-[22rem_1fr]"
  >
    <section class="flex min-h-0 flex-col">
      <h1 class="text-3xl font-semibold text-highlighted">
        {{ t('app.plots.title') }}
      </h1>
      <p
        v-if="data"
        class="mt-1 text-sm text-muted"
      >
        {{ t('app.plots.fieldCount', data.fields.features.length) }}
        · {{ t('app.plots.plotCount', data.plots.features.length) }}
      </p>
      <p class="mt-1 flex items-center gap-1.5 text-xs text-dimmed">
        <UIcon
          name="i-lucide-file-check"
          class="size-3.5"
        />
        {{ t('app.plots.provenance', { year: harvestYear }) }}
      </p>

      <div class="mt-5 min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
        <div
          v-for="group in groups"
          :key="group.field.id"
        >
          <div class="flex items-baseline justify-between gap-3 border-b border-default pb-1.5">
            <h2 class="text-sm font-semibold text-highlighted">
              {{ t('app.plots.field', { number: group.field.number }) }}
              <span
                v-if="group.field.name"
                class="font-normal text-muted"
              >· {{ group.field.name }}</span>
            </h2>
            <span class="shrink-0 text-xs text-muted">
              {{ landUseLabel(group.field.land_use_name) }} · {{ hectares(group.field.declared_area_ha) }}
            </span>
          </div>
          <ul class="mt-1.5 space-y-0.5">
            <li
              v-for="plot in group.plots"
              :key="plot.id"
            >
              <NuxtLink
                :to="localePath(`/app/plots/${plot.id}`)"
                class="flex items-center gap-3 rounded-md px-2 py-2 transition-colors"
                :class="hovered === plot.id ? 'bg-accented' : 'hover:bg-elevated'"
                data-testid="plot-row"
                @mouseenter="hovered = plot.id"
                @mouseleave="hovered = null"
                @focus="hovered = plot.id"
                @blur="hovered = null"
              >
                <span
                  class="size-3 shrink-0 rounded-sm"
                  :style="{ backgroundColor: landUseColor(plot.land_use_category) }"
                  aria-hidden="true"
                />
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-sm font-medium text-highlighted">
                    {{ landUseLabel(plot.land_use_name) }}
                  </span>
                  <span class="block text-xs text-muted">
                    {{ t('app.plots.plot', { number: plot.number }) }}
                  </span>
                </span>
                <span class="shrink-0 text-sm tabular-nums text-toned">
                  {{ hectares(plot.declared_area_ha) }}
                </span>
              </NuxtLink>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <section class="h-[60vh] min-h-80 lg:h-auto">
      <AppFarmMap
        v-if="data"
        :plots="data.plots"
        :fields="data.fields"
        :hovered-id="hovered"
        @hover="hovered = $event"
        @select="openPlot"
      />
    </section>
  </div>
</template>
