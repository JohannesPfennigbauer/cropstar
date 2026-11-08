<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type Plot = Schemas['PlotProperties']
type Task = Schemas['TaskOut']

/** What a Plot has: where its data comes from, open Tasks and the Operation Log, compactly. */
const props = defineProps<{ farmId: string, plot: Plot, members: Schemas['MemberOut'][] }>()
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const api = useApi()
const localePath = useLocalePath()
const { day, moment } = useFormat()
const { summary } = useOperationDetails()
const { lockOf } = useHarvestYear()
const today = todayIso()

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

interface Row {
  key: string
  done: boolean
  date: string | null
  title: string
  detail: string
  task?: Task
  applied?: Schemas['AppliedInput'] | null
}

// Open Tasks first, those without a date at the very top; then the log, newest first.
const rows = computed<Row[]>(() => {
  const open = [...(tasks.value ?? [])]
    .sort((a, b) => (a.due_date ?? '').localeCompare(b.due_date ?? ''))
    .map(task => ({
      key: `task-${task.id}`,
      done: false,
      date: task.due_date,
      title: task.title,
      detail: task.operation_type ? t(`app.operationTypes.${task.operation_type}`) : '',
      task
    }))
  const done = [...(log.value ?? [])]
    .sort((a, b) => (b.performed_on ?? '').localeCompare(a.performed_on ?? ''))
    .map(entry => ({
      key: `log-${entry.operation_id}`,
      done: true,
      date: entry.performed_on,
      title: `${t(`app.operationTypes.${entry.operation_type}`)} · ${entry.task_title}`,
      detail: summary(entry.actual_details, entry.actual_input),
      applied: entry.actual_input
    }))
  return [...open, ...done]
})

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
      </div>
      <div
        v-if="rows.length"
        class="mt-2 max-h-64 overflow-y-auto rounded-md border border-default"
      >
        <table
          class="w-full text-left text-xs"
          data-testid="plot-history"
        >
          <tbody class="divide-y divide-default">
            <tr
              v-for="row in rows"
              :key="row.key"
              :class="row.task ? 'cursor-pointer hover:bg-elevated' : ''"
              :data-testid="row.done ? 'plot-log-row' : 'plot-task-row'"
              @click="row.task && openEditor(row.task)"
            >
              <td class="w-6 py-1.5 pl-2 align-top">
                <UIcon
                  :name="row.done ? 'i-lucide-circle-check' : 'i-lucide-circle'"
                  class="mt-0.5 size-3.5"
                  :class="row.done ? 'text-primary' : 'text-muted'"
                  :aria-label="row.done ? t('app.tasks.status.done') : t('app.tasks.status.open')"
                />
              </td>
              <td
                class="w-24 py-1.5 align-top whitespace-nowrap tabular-nums"
                :class="row.task && isOverdue(row.task, today) ? 'font-semibold text-error' : 'text-muted'"
              >
                {{ row.date ? day(row.date) : '–' }}
              </td>
              <td class="py-1.5 pr-2 align-top">
                <span class="block font-medium text-highlighted">{{ row.title }}</span>
                <span
                  v-if="row.detail"
                  class="block text-toned"
                >{{ row.detail }}</span>
                <AppNutrientsApplied
                  v-if="row.applied"
                  :applied="row.applied"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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
