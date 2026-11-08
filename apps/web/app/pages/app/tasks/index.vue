<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

definePageMeta({ layout: 'app' })

type Task = Schemas['TaskOut']
type Stage = Schemas['TaskStageOut']

// Done Tasks stay on the board this long, then move to the archive.
const ARCHIVE_AFTER_MS = 30 * 60 * 1000
// A click waits this long to tell itself apart from a double click.
const CLICK_DELAY_MS = 250
const DONE = 'done'
const NO_DATE = 'none'
const OVERDUE = 'overdue'

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const route = useRoute()
const router = useRouter()
const { farm } = useAuth()
const { selected: harvestYear } = useHarvestYear()
const { day } = useFormat()

useSeoMeta({ title: () => t('app.tasks.title') })

const today = todayIso()
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  ticker = setInterval(() => {
    now.value = Date.now()
  }, 30_000)
})
onBeforeUnmount(() => clearInterval(ticker))

const assignee = ref('all')
const operationType = ref('all')
const showArchive = ref(false)
const plotFilter = computed(() => typeof route.query.plot === 'string' ? route.query.plot : null)

const { data: members } = await useAsyncData('members', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/members', { params: { path: { farm_id: farm.value.id } } })).data ?? []
}, { watch: [() => farm.value?.id] })

const { data: stages } = await useAsyncData('task-stages', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/task-stages', { params: { path: { farm_id: farm.value.id } } })).data ?? []
}, { watch: [() => farm.value?.id] })

const { data: operationTypes } = await useAsyncData('operation-types', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/operation-types', { params: { path: { farm_id: farm.value.id } } })).data ?? []
}, { watch: [() => farm.value?.id] })

const { data: tasks, refresh, status: loading } = await useAsyncData('tasks', async () => {
  if (!farm.value) return []
  const { data } = await api.GET('/api/farms/{farm_id}/tasks', {
    params: {
      path: { farm_id: farm.value.id },
      query: {
        assignee: assignee.value === 'all' ? undefined : assignee.value,
        harvest_year: harvestYear.value ?? undefined,
        operation_type: operationType.value === 'all' ? undefined : [operationType.value],
        plot_id: plotFilter.value ?? undefined
      }
    }
  })
  return data ?? []
}, { watch: [() => farm.value?.id, assignee, harvestYear, operationType, plotFilter] })

const assigneeItems = computed(() => [
  { label: t('app.tasks.filters.anyone'), value: 'all' },
  { label: t('app.tasks.filters.me'), value: 'me' },
  { label: t('app.tasks.filters.unassigned'), value: 'none' },
  ...(members.value ?? []).filter(m => m.assignable).map(m => ({ label: m.user.email, value: m.user.id }))
])

const typeItems = computed(() => [
  { label: t('app.operations.anyKind'), value: 'all' },
  ...(operationTypes.value ?? []).map(type => ({ label: t(`app.operationTypes.${type.code}`), value: type.code }))
])

function isArchived(task: Task): boolean {
  if (task.status === 'discarded') return true
  if (task.status !== 'done') return false
  // Imported work was done long ago; it belongs in the archive right away.
  if (task.imported) return true
  return !task.completed_at || now.value - Date.parse(task.completed_at) > ARCHIVE_AFTER_MS
}

const boardTasks = computed(() => (tasks.value ?? []).filter(task => !isArchived(task)))
const archived = computed(() => (tasks.value ?? [])
  .filter(isArchived)
  .sort((a, b) => (b.completed_at ?? b.updated_at).localeCompare(a.completed_at ?? a.updated_at)))

const columns = computed(() => [
  ...(stages.value ?? []).map(stage => ({ key: stage.id, label: stage.name })),
  { key: DONE, label: t('app.tasks.status.done') }
])

function columnOf(task: Task): string {
  if (task.status === 'done') return DONE
  const known = (stages.value ?? []).some(stage => stage.id === task.stage_id)
  return known ? task.stage_id! : stages.value?.[0]?.id ?? DONE
}

function laneOf(task: Task): string {
  if (!task.due_date) return NO_DATE
  const week = weekStartIso(task.due_date)
  return week < weekStartIso(today) ? OVERDUE : week
}

const lanes = computed(() => {
  const keys = new Set(boardTasks.value.map(laneOf))
  const weeks = [...keys].filter(key => key !== NO_DATE && key !== OVERDUE).sort()
  return [...(keys.has(NO_DATE) ? [NO_DATE] : []), ...(keys.has(OVERDUE) ? [OVERDUE] : []), ...weeks]
    .map(key => ({ key, label: laneLabel(key) }))
})

function laneLabel(key: string): string {
  if (key === NO_DATE) return t('app.tasks.board.noDate')
  if (key === OVERDUE) return t('app.tasks.board.overdue')
  const label = t('app.tasks.board.week', { week: isoWeek(key), from: day(key), to: day(addDaysIso(key, 6)) })
  return key === weekStartIso(today) ? `${label} · ${t('app.tasks.board.thisWeek')}` : label
}

function cards(lane: string, column: string): Task[] {
  return boardTasks.value
    .filter(task => laneOf(task) === lane && columnOf(task) === column)
    .sort((a, b) => (a.due_date ?? '').localeCompare(b.due_date ?? '') || a.title.localeCompare(b.title))
}

// ── Editing ────────────────────────────────────────────────────────────────
const editorOpen = ref(false)
const editing = ref<Task | null>(null)
function openEditor(task: Task | null) {
  editing.value = task
  editorOpen.value = true
}

const completing = ref(false)
const completingTask = ref<Task | null>(null)

async function changed() {
  await refresh()
  if (editing.value) editing.value = tasks.value?.find(item => item.id === editing.value?.id) ?? editing.value
}

// ── One click moves a Task on, a double click opens it ────────────────────
let pending: ReturnType<typeof setTimeout> | undefined
function onClick(task: Task) {
  clearTimeout(pending)
  pending = setTimeout(() => advance(task), CLICK_DELAY_MS)
}
function onDoubleClick(task: Task) {
  clearTimeout(pending)
  openEditor(task)
}

function refuse(reason: string) {
  toast.add({ title: t(`app.tasks.board.refused.${reason}`), color: 'warning', icon: 'i-lucide-ban' })
}

async function setStage(task: Task, stageId: string) {
  const { data } = await api.PATCH('/api/farms/{farm_id}/tasks/{task_id}', {
    params: { path: { farm_id: farm.value!.id, task_id: task.id } },
    body: { stage_id: stageId }
  })
  return data
}

async function command(task: Task, name: 'complete' | 'reopen') {
  const { data } = await api.POST('/api/farms/{farm_id}/tasks/{task_id}/{command}', {
    params: { path: { farm_id: farm.value!.id, task_id: task.id, command: name } }
  })
  return data
}

async function advance(task: Task) {
  if (task.status !== 'open') return
  const order = (stages.value ?? []).map(stage => stage.id)
  const index = Math.max(0, order.indexOf(columnOf(task)))
  if (index < order.length - 1) {
    if (!task.allowed_actions.includes('edit_task')) return refuse(task.harvest_year ? 'locked' : 'role')
    const before = columnOf(task)
    const next = order[index + 1]!
    if (!await setStage(task, next)) return refuse('failed')
    await refresh()
    toast.add({
      title: t('app.tasks.board.moved', { task: task.title, stage: stageName(next) }),
      color: 'neutral',
      icon: 'i-lucide-arrow-right',
      actions: [{ label: t('app.tasks.board.undo'), onClick: () => undo(() => setStage(task, before)) }]
    })
    return
  }
  if (!task.allowed_actions.includes('complete_task')) {
    return refuse(task.allowed_actions.includes('edit_task') ? 'role' : 'locked')
  }
  // Recording work is a decision about what really happened: Operations get their dialog.
  if (task.operation_type) {
    completingTask.value = task
    completing.value = true
    return
  }
  if (!await command(task, 'complete')) return refuse('failed')
  await refresh()
  toast.add({
    title: t('app.tasks.board.done', { task: task.title }),
    color: 'success',
    icon: 'i-lucide-check',
    actions: [{ label: t('app.tasks.board.undo'), onClick: () => undo(() => command(task, 'reopen')) }]
  })
}

async function undo(revert: () => Promise<unknown>) {
  await revert()
  await refresh()
}

function stageName(id: string): string {
  return stages.value?.find((stage: Stage) => stage.id === id)?.name ?? ''
}

function clearPlotFilter() {
  const query = { ...route.query }
  delete query.plot
  router.replace({ query })
}

// The filtered Plot's name, from any Task that refers to it.
const plotLabel = computed(() => {
  for (const task of tasks.value ?? []) {
    const plot = task.plots.find(p => p.id === plotFilter.value)
    if (plot) return `${t('app.tasks.plotRef', { field: plot.field_number, plot: plot.number })} · ${landUseLabel(plot.land_use_name)}`
  }
  return t('app.tasks.board.onePlot')
})

/** "Düngung" for one Plot, "Düngung · 1/2" with progress across several. */
function operationBadge(task: Task) {
  const kind = t(`app.operationTypes.${task.operation_type}`)
  const counted = task.operations.filter(o => o.status !== 'discarded')
  if (task.operations.length < 2) return kind
  return `${kind} · ${counted.filter(o => o.status === 'done').length}/${counted.length}`
}

const PRIORITY_COLOR = { high: 'error', normal: 'warning', low: 'neutral', none: 'neutral' } as const
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-3xl font-semibold text-highlighted">
        {{ t('app.tasks.title') }}
      </h1>
      <UButton
        icon="i-lucide-plus"
        :label="t('app.tasks.new')"
        data-testid="new-task"
        @click="openEditor(null)"
      />
    </div>

    <AppLockNotice
      :year="harvestYear"
      class="mt-4"
    />

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <USelect
        v-model="assignee"
        :items="assigneeItems"
        size="sm"
        icon="i-lucide-user"
        class="w-44"
        :aria-label="t('app.tasks.fields.assignee')"
      />
      <USelect
        v-model="operationType"
        :items="typeItems"
        size="sm"
        icon="i-lucide-tractor"
        class="w-44"
        :aria-label="t('app.operations.kind')"
      />
      <UBadge
        v-if="plotFilter"
        color="primary"
        variant="subtle"
        class="gap-1.5"
        data-testid="plot-filter"
      >
        <UIcon
          name="i-lucide-map-pin"
          class="size-3.5"
        />
        {{ plotLabel }}
        <button
          type="button"
          class="ml-1"
          :aria-label="t('app.tasks.board.clearPlot')"
          @click="clearPlotFilter"
        >
          <UIcon
            name="i-lucide-x"
            class="size-3.5"
          />
        </button>
      </UBadge>
      <UButton
        class="ml-auto"
        size="sm"
        color="neutral"
        :variant="showArchive ? 'soft' : 'ghost'"
        icon="i-lucide-archive"
        :label="t('app.tasks.board.archive', { n: archived.length })"
        :aria-pressed="showArchive"
        data-testid="show-archive"
        @click="showArchive = !showArchive"
      />
    </div>
    <p class="mt-2 text-xs text-dimmed">
      {{ t('app.tasks.board.hint') }}
    </p>

    <section
      v-if="showArchive"
      class="mt-4"
      data-testid="task-archive"
    >
      <ul
        v-if="archived.length"
        class="divide-y divide-default rounded-lg border border-default"
      >
        <li
          v-for="task in archived"
          :key="task.id"
        >
          <button
            type="button"
            class="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-elevated"
            data-testid="task-row"
            @click="openEditor(task)"
          >
            <UIcon
              :name="task.status === 'done' ? 'i-lucide-circle-check' : 'i-lucide-archive'"
              class="size-4 shrink-0"
              :class="task.status === 'done' ? 'text-primary' : 'text-muted'"
            />
            <span class="min-w-0 flex-1 truncate text-toned">{{ task.title }}</span>
            <UBadge
              v-if="task.operation_type"
              color="primary"
              variant="subtle"
              size="sm"
              :label="operationBadge(task)"
            />
            <span class="shrink-0 text-xs text-muted">
              {{ t(`app.tasks.status.${task.status}`) }}<template v-if="task.completed_at"> · {{ day(task.completed_at.slice(0, 10)) }}</template>
            </span>
          </button>
        </li>
      </ul>
      <p
        v-else
        class="text-sm text-muted"
      >
        {{ t('app.tasks.board.archiveEmpty') }}
      </p>
    </section>

    <div
      v-else-if="lanes.length"
      class="mt-4 overflow-x-auto pb-2"
      data-testid="task-board"
    >
      <div
        class="grid min-w-[48rem] gap-x-3"
        :style="{ gridTemplateColumns: `repeat(${columns.length}, minmax(11rem, 1fr))` }"
      >
        <div
          v-for="column in columns"
          :key="column.key"
          class="sticky top-0 z-10 border-b-2 border-default bg-default pb-1.5 text-xs font-semibold tracking-wide text-muted uppercase"
          data-testid="board-column"
        >
          {{ column.label }}
        </div>
        <template
          v-for="lane in lanes"
          :key="lane.key"
        >
          <div
            class="mt-4 mb-1.5 flex items-center gap-2 text-sm font-semibold"
            :class="lane.key === OVERDUE ? 'text-error' : 'text-highlighted'"
            :style="{ gridColumn: `1 / span ${columns.length}` }"
            data-testid="board-lane"
          >
            <UIcon
              :name="lane.key === NO_DATE ? 'i-lucide-calendar-off' : lane.key === OVERDUE ? 'i-lucide-alarm-clock' : 'i-lucide-calendar'"
              class="size-4"
            />
            {{ lane.label }}
          </div>
          <div
            v-for="column in columns"
            :key="`${lane.key}-${column.key}`"
            class="min-h-12 space-y-2 rounded-lg bg-elevated/50 p-1.5"
          >
            <div
              v-for="task in cards(lane.key, column.key)"
              :key="task.id"
              role="button"
              tabindex="0"
              class="group cursor-pointer rounded-md border border-default bg-default p-2.5 text-sm shadow-xs transition-colors select-none hover:border-primary/60"
              :class="{ 'opacity-70': task.status === 'done' }"
              :aria-label="t('app.tasks.board.cardLabel', { task: task.title })"
              data-testid="task-card"
              @click="onClick(task)"
              @dblclick="onDoubleClick(task)"
              @keydown.enter.prevent="advance(task)"
              @keydown.space.prevent="openEditor(task)"
            >
              <div class="flex items-start gap-2">
                <span
                  class="min-w-0 flex-1 font-medium"
                  :class="task.status === 'done' ? 'text-muted line-through decoration-1' : 'text-highlighted'"
                >
                  {{ task.title }}
                </span>
                <button
                  type="button"
                  class="-m-1 shrink-0 rounded p-1 text-muted hover:text-highlighted"
                  :aria-label="t('app.tasks.board.edit')"
                  data-testid="task-edit"
                  @click.stop="openEditor(task)"
                  @dblclick.stop
                >
                  <UIcon
                    name="i-lucide-pencil"
                    class="size-3.5"
                  />
                </button>
              </div>
              <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                <span
                  v-if="task.due_date"
                  class="flex items-center gap-1"
                  :class="{ 'font-semibold text-error': isOverdue(task, today) }"
                >
                  <UIcon
                    name="i-lucide-calendar"
                    class="size-3.5"
                  />
                  {{ day(task.due_date) }}
                </span>
                <UBadge
                  v-if="task.operation_type"
                  color="primary"
                  variant="subtle"
                  size="sm"
                  :label="operationBadge(task)"
                  data-testid="operation-badge"
                />
                <UBadge
                  v-if="task.priority !== 'none'"
                  :color="PRIORITY_COLOR[task.priority]"
                  variant="subtle"
                  size="sm"
                  :label="t(`app.tasks.priority.${task.priority}`)"
                />
                <span
                  v-if="task.assignee"
                  class="flex items-center gap-1"
                >
                  <UIcon
                    name="i-lucide-user"
                    class="size-3.5"
                  />
                  {{ task.assignee.email }}
                </span>
                <AppTaskAreas :task="task" />
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <UAlert
      v-else-if="loading !== 'pending'"
      class="mt-6"
      color="neutral"
      variant="subtle"
      icon="i-lucide-list-checks"
      :title="t('app.tasks.emptyTitle')"
      :description="t('app.tasks.empty')"
    />

    <AppTaskEditor
      v-if="farm"
      v-model:open="editorOpen"
      :farm-id="farm.id"
      :task="editing"
      :members="members ?? []"
      :harvest-year="harvestYear"
      @changed="changed()"
    />
    <AppCompleteOperations
      v-if="farm && completingTask"
      v-model:open="completing"
      :farm-id="farm.id"
      :task="completingTask"
      @changed="changed()"
    />
  </div>
</template>
