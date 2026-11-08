<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'
import type { Activity } from '~/utils/activities'

type Plot = Schemas['PlotProperties']
type Task = Schemas['TaskOut']

/** What a Plot has: where its data comes from, open Tasks and the Operation Log, compactly. */
const props = defineProps<{ farmId: string, plot: Plot, members: Schemas['MemberOut'][] }>()
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const api = useApi()
const localePath = useLocalePath()
const { moment } = useFormat()
const { summary } = useOperationDetails()
const { lockOf } = useHarvestYear()

const { data: tasks, refresh: refreshTasks } = useAsyncData(
  () => `plot-tasks-${props.plot.id}`,
  async () => (await api.GET('/api/farms/{farm_id}/tasks', {
    params: { path: { farm_id: props.farmId }, query: { plot_id: props.plot.id, status: ['open'] } }
  })).data ?? [],
  { watch: [() => props.plot.id] }
)
const { data: log, refresh: refreshLog } = useAsyncData(
  () => `plot-log-${props.plot.id}`,
  async () => (await api.GET('/api/farms/{farm_id}/plots/{plot_id}/operations', {
    params: { path: { farm_id: props.farmId, plot_id: props.plot.id } }
  })).data ?? [],
  { watch: [() => props.plot.id] }
)

const locked = computed(() => lockOf(props.plot.harvest_year) !== null)

const source = computed(() => t(`app.plots.sourceValue.${props.plot.provenance.source}`, {
  year: props.plot.harvest_year,
  date: moment(props.plot.provenance.imported_at),
  from: props.plot.provenance.borrowed_from_year
}))

// Activities: Open Tasks and the Operation Log of this Plot, shown as a spiral (default) or a table.
const activities = computed<Activity[]>(() => [
  ...(tasks.value ?? []).map(task => ({
    key: `task-${task.id}`,
    done: false,
    date: task.due_date,
    title: task.title,
    detail: task.operation_type ? t(`app.operationTypes.${task.operation_type}`) : '',
    operationType: task.operation_type,
    priority: task.priority,
    task
  })),
  ...(log.value ?? []).map(entry => ({
    key: `log-${entry.operation_id}`,
    done: true,
    // An Operation recorded without a day counts on the day it was completed.
    date: entry.performed_on ?? entry.completed_at?.slice(0, 10) ?? null,
    title: `${t(`app.operationTypes.${entry.operation_type}`)} · ${entry.task_title}`,
    detail: summary(entry.actual_details, entry.actual_input),
    operationType: entry.operation_type,
    priority: 'none' as const,
    applied: entry.actual_input
  }))
])

const view = useState<'spiral' | 'table'>('plot-activities-view', () => 'spiral')

const editorOpen = ref(false)
const editing = ref<Task | null>(null)
function openEditor(task: Task | null) {
  editing.value = task
  editorOpen.value = true
}

async function changed() {
  await Promise.all([refreshTasks(), refreshLog()])
  emit('changed')
}
</script>

<template>
  <div
    class="space-y-3 border-l-2 border-primary/40 py-2 pr-1 pl-3 text-sm"
    data-testid="plot-panel"
  >
    <p
      class="flex items-start gap-1.5 text-xs text-muted"
      data-testid="plot-source"
    >
      <UIcon
        name="i-lucide-file-check"
        class="mt-0.5 size-3.5 shrink-0"
      />
      {{ source }}
    </p>
    <AppLockNotice :year="plot.harvest_year" />

    <div>
      <div class="flex items-center justify-between gap-2">
        <ULink
          :to="localePath({ path: '/app/tasks', query: { plot: plot.id } })"
          class="inline-flex items-center gap-1 font-semibold text-highlighted hover:text-primary"
          data-testid="plot-history-link"
        >
          {{ t('app.plots.history') }}
          <UIcon
            name="i-lucide-arrow-right"
            class="size-3.5"
          />
        </ULink>
        <div class="flex items-center gap-2">
          <UButton
            size="xs"
            variant="soft"
            icon="i-lucide-plus"
            :label="t('app.plots.newTask')"
            :disabled="locked"
            :title="locked ? t('app.harvestYear.locked', { year: plot.harvest_year }) : undefined"
            data-testid="new-plot-task"
            @click="openEditor(null)"
          />
          <div
            class="flex rounded-md border border-default p-0.5"
            role="group"
            :aria-label="t('app.activities.view.label')"
          >
            <UButton
              size="xs"
              :variant="view === 'table' ? 'soft' : 'ghost'"
              :color="view === 'table' ? 'primary' : 'neutral'"
              icon="i-lucide-table-2"
              :aria-label="t('app.activities.view.table')"
              :aria-pressed="view === 'table'"
              :title="t('app.activities.view.table')"
              data-testid="activities-view-table"
              @click="view = 'table'"
            />
            <UButton
              size="xs"
              :variant="view === 'spiral' ? 'soft' : 'ghost'"
              :color="view === 'spiral' ? 'primary' : 'neutral'"
              icon="i-lucide-orbit"
              :aria-label="t('app.activities.view.spiral')"
              :aria-pressed="view === 'spiral'"
              :title="t('app.activities.view.spiral')"
              data-testid="activities-view-spiral"
              @click="view = 'spiral'"
            />
          </div>
        </div>
      </div>
      <template v-if="activities.length">
        <AppActivitySpiral
          v-if="view === 'spiral'"
          :activities="activities"
          @select="activity => activity.task && openEditor(activity.task)"
        />
        <AppActivityTable
          v-else
          :activities="activities"
          @select="activity => activity.task && openEditor(activity.task)"
        />
      </template>
      <p
        v-else
        class="mt-1 text-xs text-muted"
      >
        {{ t('app.plots.historyEmpty') }}
      </p>
    </div>

    <AppTaskEditor
      v-model:open="editorOpen"
      :farm-id="farmId"
      :task="editing"
      :members="members"
      :harvest-year="plot.harvest_year"
      :preset-plot-ids="[plot.id]"
      @changed="changed()"
    />
  </div>
</template>
