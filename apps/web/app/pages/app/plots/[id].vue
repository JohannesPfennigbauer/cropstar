<script setup lang="ts">
definePageMeta({ layout: 'app' })

const { t } = useI18n()
const api = useApi()
const route = useRoute()
const localePath = useLocalePath()
const { farm } = useAuth()
const { hectares, day } = useFormat()
const today = todayIso()

const plotId = computed(() => String(route.params.id))

const { data: plot, status } = await useAsyncData(`plot-${plotId.value}`, async () => {
  if (!farm.value) return null
  const { data } = await api.GET('/api/farms/{farm_id}/plots/{plot_id}', {
    params: { path: { farm_id: farm.value.id, plot_id: plotId.value } }
  })
  return data ?? null
}, { watch: [plotId, () => farm.value?.id] })

const { data: tasks, refresh: refreshTasks } = await useAsyncData(`plot-tasks-${plotId.value}`, async () => {
  if (!farm.value) return []
  const { data } = await api.GET('/api/farms/{farm_id}/tasks', {
    params: { path: { farm_id: farm.value.id }, query: { plot_id: plotId.value, status: ['open'] } }
  })
  return data ?? []
}, { watch: [plotId, () => farm.value?.id] })

const { data: members } = await useAsyncData('members', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/members', { params: { path: { farm_id: farm.value.id } } })).data ?? []
}, { watch: [() => farm.value?.id] })

const { data: log, refresh: refreshLog } = await useAsyncData(`plot-log-${plotId.value}`, async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/plots/{plot_id}/operations', {
    params: { path: { farm_id: farm.value.id, plot_id: plotId.value } }
  })).data ?? []
}, { watch: [plotId, () => farm.value?.id] })

async function changed() {
  await Promise.all([refreshTasks(), refreshLog()])
  if (editing.value) {
    // A Task that is no longer open drops out of this list; fetch it directly instead.
    const { data } = await api.GET('/api/farms/{farm_id}/tasks/{task_id}', {
      params: { path: { farm_id: farm.value!.id, task_id: editing.value.id } }
    })
    if (data) editing.value = data
  }
}

const editorOpen = ref(false)
const editing = ref<NonNullable<typeof tasks.value>[number] | null>(null)
function openEditor(task: typeof editing.value) {
  editing.value = task
  editorOpen.value = true
}

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
            <div class="flex items-center justify-between gap-3">
              <h2 class="font-semibold text-highlighted">
                {{ t('app.plots.tasks') }}
              </h2>
              <UButton
                size="sm"
                variant="soft"
                icon="i-lucide-plus"
                :label="t('app.plots.newTask')"
                data-testid="new-plot-task"
                @click="openEditor(null)"
              />
            </div>
            <ul
              v-if="tasks?.length"
              class="mt-3 divide-y divide-default"
            >
              <li
                v-for="task in tasks"
                :key="task.id"
              >
                <button
                  type="button"
                  class="w-full py-2 text-left"
                  data-testid="plot-task"
                  @click="openEditor(task)"
                >
                  <span class="block text-sm font-medium text-highlighted">{{ task.title }}</span>
                  <span
                    v-if="task.due_date"
                    class="text-xs"
                    :class="isOverdue(task, today) ? 'font-semibold text-error' : 'text-muted'"
                  >
                    {{ day(task.due_date) }}<template v-if="isOverdue(task, today)"> · {{ t('app.tasks.overdue') }}</template>
                  </span>
                </button>
              </li>
            </ul>
            <p
              v-else
              class="mt-2 text-sm text-muted"
            >
              {{ t('app.plots.noTasks') }}
            </p>
          </UCard>

          <UCard>
            <h2 class="font-semibold text-highlighted">
              {{ t('app.plots.log') }}
            </h2>
            <ol
              v-if="log?.length"
              class="mt-3 space-y-3 border-l border-default pl-4"
              data-testid="operation-log"
            >
              <li
                v-for="entry in log"
                :key="entry.operation_id"
                class="relative text-sm"
              >
                <span
                  class="absolute top-1.5 -left-[1.3rem] size-2 rounded-full bg-primary"
                  aria-hidden="true"
                />
                <span class="block text-xs text-muted">
                  {{ entry.performed_on ? day(entry.performed_on) : '–' }}
                </span>
                <span class="block font-medium text-highlighted">
                  {{ t(`app.operationTypes.${entry.operation_type}`) }} · {{ entry.task_title }}
                </span>
                <span
                  v-if="entry.actual_details"
                  class="block text-toned"
                >{{ entry.actual_details }}</span>
                <span class="block text-xs text-dimmed">{{ entry.completed_by?.email ?? t('app.tasks.formerMember') }}</span>
              </li>
            </ol>
            <p
              v-else
              class="mt-1 text-sm text-muted"
            >
              {{ t('app.plots.logEmpty') }}
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

      <AppTaskEditor
        v-if="farm"
        v-model:open="editorOpen"
        :farm-id="farm.id"
        :task="editing"
        :members="members ?? []"
        :harvest-year="plot.properties.harvest_year"
        :preset-plot-ids="[plot.id]"
        @changed="changed()"
      />
    </template>
  </div>
</template>
