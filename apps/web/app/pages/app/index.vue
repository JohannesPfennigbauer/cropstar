<script setup lang="ts">
definePageMeta({ layout: 'app' })

const { t } = useI18n()
const api = useApi()
const route = useRoute()
const router = useRouter()
const { farm, membership } = useAuth()
const { selected: harvestYear, years, load: loadHarvestYears } = useHarvestYear()
const { hectares, moment } = useFormat()

const isAdmin = computed(() => membership.value?.role === 'admin')
const creating = ref(false)
const uploadOpen = ref(false)

useSeoMeta({ title: () => t('app.nav.home') })

async function onUploaded(year: number) {
  await loadHarvestYears()
  // A re-upload into the shown year changes its areas without changing the year.
  if (harvestYear.value === year) await refresh()
  else harvestYear.value = year
}

const { data, status, refresh } = await useAsyncData('overview-areas', async () => {
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

const { data: members } = await useAsyncData('members', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/members', { params: { path: { farm_id: farm.value.id } } })).data ?? []
}, { watch: [() => farm.value?.id] })

// The open Plot lives in the address, so it survives a reload and can be linked to.
const selected = computed(() => {
  const id = typeof route.query.plot === 'string' ? route.query.plot : null
  return id && data.value?.plots.features.some(f => f.id === id) ? id : null
})

function select(id: string | null) {
  const query = { ...route.query }
  if (id === null || id === selected.value) delete query.plot
  else query.plot = id
  router.replace({ query })
}

const hovered = ref<string | null>(null)

// One line for the year: imported areas may mix borrowed geometry and none at all.
const provenance = computed(() => {
  const features = data.value?.plots.features ?? []
  const first = features.find(f => f.properties.provenance.source !== 'none') ?? features[0] ?? data.value?.fields.features[0]
  if (!first) return null
  const { source, imported_at, borrowed_from_year } = first.properties.provenance
  const text = t(`app.plots.provenance.${source}`, { year: harvestYear.value, date: moment(imported_at), from: borrowed_from_year })
  const missing = features.filter(f => f.geometry === null).length
  return missing && source !== 'none' ? `${text} · ${t('app.plots.withoutGeometry', missing)}` : text
})

const groups = computed(() => {
  if (!data.value) return []
  return data.value.fields.features.map(field => ({
    field: field.properties,
    plots: data.value!.plots.features
      .filter(plot => plot.properties.field.id === field.id)
      .map(plot => plot.properties)
  }))
})

// Keep the open Plot in view when it is opened from the map.
watch(selected, async (id) => {
  if (!id || !import.meta.client) return
  await nextTick()
  document.querySelector(`[data-plot-id="${id}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})
</script>

<template>
  <div
    v-if="!farm"
    class="max-w-2xl"
  >
    <h1 class="text-3xl font-semibold text-highlighted sm:text-4xl">
      {{ t('app.farm.noneTitle') }}
    </h1>
    <p class="mt-3 text-lg text-muted">
      {{ t('app.farm.noneLead') }}
    </p>
    <UButton
      class="mt-6"
      icon="i-lucide-plus"
      :label="t('app.farm.createTitle')"
      @click="creating = true"
    />
    <AppCreateFarmDialog v-model:open="creating" />
  </div>

  <div v-else>
    <div
      v-if="years.length === 0 && status !== 'pending'"
      class="max-w-2xl"
    >
      <h1 class="text-3xl font-semibold text-highlighted">
        {{ farm.name }}
      </h1>
      <UAlert
        class="mt-6"
        color="neutral"
        variant="subtle"
        icon="i-lucide-map"
        :title="t('app.plots.emptyTitle')"
        :description="isAdmin ? t('app.plots.empty') : t('app.plots.emptyReadOnly')"
      >
        <template
          v-if="isAdmin"
          #actions
        >
          <UButton
            icon="i-lucide-upload"
            :label="t('app.plots.upload')"
            data-testid="upload-areas"
            @click="uploadOpen = true"
          />
        </template>
      </UAlert>
    </div>

    <div
      v-else
      class="grid gap-6 lg:h-[calc(100dvh-9rem)] lg:grid-cols-[2fr_3fr]"
    >
      <section class="flex min-h-0 flex-col">
        <div class="flex items-center justify-between gap-3">
          <h1 class="truncate text-3xl font-semibold text-highlighted">
            {{ farm.name }}
          </h1>
          <UButton
            v-if="isAdmin"
            icon="i-lucide-upload"
            color="neutral"
            variant="outline"
            size="sm"
            :label="t('app.plots.upload')"
            data-testid="upload-areas"
            @click="uploadOpen = true"
          />
        </div>
        <p
          v-if="data"
          class="mt-1 text-sm text-muted"
        >
          {{ t('app.plots.fieldCount', data.fields.features.length) }}
          · {{ t('app.plots.plotCount', data.plots.features.length) }}
        </p>
        <p
          v-if="provenance"
          class="mt-1 flex items-center gap-1.5 text-xs text-dimmed"
          data-testid="plots-provenance"
        >
          <UIcon
            name="i-lucide-file-check"
            class="size-3.5 shrink-0"
          />
          {{ provenance }}
        </p>
        <AppLockNotice
          :year="harvestYear"
          class="mt-3"
        />

        <div class="mt-5 min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
          <div
            v-for="group in groups"
            :key="group.field.id"
          >
            <div class="flex items-baseline justify-between gap-3 border-b border-default pb-1.5">
              <h2
                class="flex min-w-0 items-baseline gap-2 text-sm"
                :aria-label="[t('app.plots.field', { number: group.field.number }), group.field.name].filter(Boolean).join(' · ')"
                data-testid="field-heading"
              >
                <span class="tabular-nums text-muted">{{ group.field.number }}</span>
                <span class="truncate font-semibold text-highlighted">{{ group.field.name ?? t('app.plots.field', { number: group.field.number }) }}</span>
              </h2>
              <span class="shrink-0 text-xs text-muted">
                {{ landUseLabel(group.field.land_use_name) }} · {{ hectares(group.field.declared_area_ha) }}
              </span>
            </div>
            <ul class="mt-1.5 space-y-0.5">
              <li
                v-for="plot in group.plots"
                :key="plot.id"
                :data-plot-id="plot.id"
              >
                <button
                  type="button"
                  class="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left transition-colors"
                  :class="selected === plot.id ? 'bg-accented' : hovered === plot.id ? 'bg-elevated' : 'hover:bg-elevated'"
                  :aria-expanded="selected === plot.id"
                  data-testid="plot-row"
                  @click="select(plot.id)"
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
                      <template v-if="plot.provenance.source === 'borrowed'">
                        · {{ t('app.plots.provisional') }}
                      </template>
                      <template v-else-if="plot.provenance.source === 'none'">
                        · {{ t('app.plots.noGeometry') }}
                      </template>
                    </span>
                  </span>
                  <span class="shrink-0 text-sm tabular-nums text-toned">
                    {{ hectares(plot.declared_area_ha) }}
                  </span>
                  <UIcon
                    :name="selected === plot.id ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                    class="size-4 shrink-0 text-muted"
                  />
                </button>
                <AppPlotPanel
                  v-if="selected === plot.id"
                  class="mt-1 mb-3 ml-2"
                  :farm-id="farm.id"
                  :plot="plot"
                  :members="members ?? []"
                />
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
          :selected-id="selected"
          @hover="hovered = $event"
          @select="select"
        />
      </section>
    </div>

    <AppAreaUploadDialog
      v-if="isAdmin"
      v-model:open="uploadOpen"
      @uploaded="onUploaded"
    />
  </div>
</template>
