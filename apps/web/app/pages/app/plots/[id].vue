<script setup lang="ts">
definePageMeta({ layout: 'app' })

const { t } = useI18n()
const api = useApi()
const route = useRoute()
const localePath = useLocalePath()
const { farm } = useAuth()
const { hectares } = useFormat()

const plotId = computed(() => String(route.params.id))

const { data: plot, status } = await useAsyncData(`plot-${plotId.value}`, async () => {
  if (!farm.value) return null
  const { data } = await api.GET('/api/farms/{farm_id}/plots/{plot_id}', {
    params: { path: { farm_id: farm.value.id, plot_id: plotId.value } }
  })
  return data ?? null
}, { watch: [plotId, () => farm.value?.id] })

const collection = computed(() => plot.value
  ? { type: 'FeatureCollection' as const, features: [plot.value] }
  : null)

const title = computed(() => plot.value
  ? `${t('app.plots.plot', { number: plot.value.properties.number })} · ${landUseLabel(plot.value.properties.land_use_name)}`
  : t('app.plots.title'))

useSeoMeta({ title })
</script>

<template>
  <div>
    <ULink
      :to="localePath('/app/plots')"
      class="inline-flex items-center gap-1 text-sm text-muted hover:text-highlighted"
    >
      <UIcon
        name="i-lucide-arrow-left"
        class="size-4"
      />
      {{ t('app.plots.back') }}
    </ULink>

    <UAlert
      v-if="!plot && status !== 'pending'"
      class="mt-6 max-w-xl"
      color="neutral"
      variant="subtle"
      icon="i-lucide-map-pin-off"
      :description="t('app.plots.notFound')"
    />

    <template v-else-if="plot">
      <h1 class="mt-3 text-3xl font-semibold text-highlighted">
        {{ title }}
      </h1>
      <p class="mt-1 text-muted">
        {{ t('app.plots.field', { number: plot.properties.field.number }) }}<template v-if="plot.properties.field.name">
          · {{ plot.properties.field.name }}
        </template>
        · {{ t('app.harvestYear.option', { year: plot.properties.harvest_year }) }}
      </p>

      <div class="mt-6 grid gap-6 lg:grid-cols-[22rem_1fr]">
        <div class="space-y-6">
          <UCard>
            <dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
              <dt class="text-muted">
                {{ t('app.plots.landUse') }}
              </dt>
              <dd class="flex items-center gap-2 text-highlighted">
                <span
                  class="size-3 rounded-sm"
                  :style="{ backgroundColor: landUseColor(plot.properties.land_use_category) }"
                  aria-hidden="true"
                />
                {{ landUseLabel(plot.properties.land_use_name) }}
                <span class="text-xs text-dimmed">({{ plot.properties.land_use_code }})</span>
              </dd>
              <dt class="text-muted">
                {{ t('app.plots.category') }}
              </dt>
              <dd class="text-highlighted">
                {{ t(`app.landUseCategory.${plot.properties.land_use_category}`) }}
              </dd>
              <dt class="text-muted">
                {{ t('app.plots.declaredArea') }}
              </dt>
              <dd class="tabular-nums text-highlighted">
                {{ hectares(plot.properties.declared_area_ha, 4) }}
              </dd>
              <dt class="text-muted">
                {{ t('app.plots.source') }}
              </dt>
              <dd class="text-highlighted">
                {{ t('app.plots.sourceValue', { year: plot.properties.harvest_year }) }}
              </dd>
            </dl>
          </UCard>

          <UCard>
            <h2 class="font-semibold text-highlighted">
              {{ t('app.plots.tasks') }}
            </h2>
            <p class="mt-1 text-sm text-muted">
              {{ t('app.plots.tasksSoon') }}
            </p>
          </UCard>

          <UCard>
            <h2 class="font-semibold text-highlighted">
              {{ t('app.plots.log') }}
            </h2>
            <p class="mt-1 text-sm text-muted">
              {{ t('app.plots.logSoon') }}
            </p>
          </UCard>
        </div>

        <section class="h-[50vh] min-h-80 lg:h-[calc(100dvh-14rem)]">
          <AppFarmMap
            v-if="collection"
            :plots="collection"
            :selected-id="plot.id"
          />
        </section>
      </div>
    </template>
  </div>
</template>
