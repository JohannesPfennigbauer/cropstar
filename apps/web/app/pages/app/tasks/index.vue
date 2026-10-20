<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

definePageMeta({ layout: 'app' })

type Task = Schemas['TaskOut']
type StatusFilter = 'open' | 'done' | 'discarded' | 'all'
type DueFilter = 'all' | 'overdue' | 'week' | 'none'

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { farm } = useAuth()
const { selected: harvestYear } = useHarvestYear()
const { day } = useFormat()

useSeoMeta({ title: () => t('app.tasks.title') })

const status = ref<StatusFilter>('open')
const assignee = ref('all')
const priority = ref<'all' | Schemas['Priority']>('all')
const due = ref<DueFilter>('all')
const operationType = ref('all')
const today = todayIso()

const { data: members } = await useAsyncData('members', async () => {
  if (!farm.value) return []
  const { data } = await api.GET('/api/farms/{farm_id}/members', {
    params: { path: { farm_id: farm.value.id } }
  })
  return data ?? []
}, { watch: [() => farm.value?.id] })

const { data: tasks, refresh, status: loading } = await useAsyncData('tasks', async () => {
  if (!farm.value) return []
  const { data } = await api.GET('/api/farms/{farm_id}/tasks', {
    params: {
      path: { farm_id: farm.value.id },
      query: {
        status: status.value === 'all' ? undefined : [status.value],
        assignee: assignee.value === 'all' ? undefined : assignee.value,
        priority: priority.value === 'all' ? undefined : [priority.value],
        due_before: due.value === 'overdue'
          ? addDaysIso(today, -1)
          : due.value === 'week' ? addDaysIso(today, 7) : undefined,
        without_due: due.value === 'none' || undefined,
        harvest_year: harvestYear.value ?? undefined,
        operation_type: operationType.value === 'all' ? undefined : [operationType.value]
      }
    }
  })
  return data ?? []
}, { watch: [() => farm.value?.id, status, assignee, priority, due, harvestYear, operationType] })

const statusTabs = computed(() => (['open', 'done', 'discarded', 'all'] as const)
  .map(value => ({ label: t(`app.tasks.filters.status.${value}`), value })))

const assigneeItems = computed(() => [
  { label: t('app.tasks.filters.anyone'), value: 'all' },
  { label: t('app.tasks.filters.me'), value: 'me' },
  { label: t('app.tasks.filters.unassigned'), value: 'none' },
  ...(members.value ?? []).filter(m => m.assignable).map(m => ({ label: m.user.email, value: m.user.id }))
])

const priorityItems = computed(() => [
  { label: t('app.tasks.filters.anyPriority'), value: 'all' as const },
  ...(['high', 'normal', 'low', 'none'] as const).map(value => ({ label: t(`app.tasks.priority.${value}`), value }))
])

const { data: operationTypes } = await useAsyncData('operation-types', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/operation-types', {
    params: { path: { farm_id: farm.value.id } }
  })).data ?? []
}, { watch: [() => farm.value?.id] })

const typeItems = computed(() => [
  { label: t('app.operations.anyKind'), value: 'all' },
  ...(operationTypes.value ?? []).map(type => ({ label: t(`app.operationTypes.${type.code}`), value: type.code }))
])

const dueItems = computed(() => (['all', 'overdue', 'week', 'none'] as const)
  .map(value => ({ label: t(`app.tasks.filters.due.${value}`), value })))

const editorOpen = ref(false)
const editing = ref<Task | null>(null)

function openEditor(task: Task | null) {
  editing.value = task
  editorOpen.value = true
}

const completing = ref(false)
const completingTask = ref<Task | null>(null)

/** After any change, show the fresh version of the Task being looked at. */
async function changed() {
  await refresh()
  if (editing.value) editing.value = tasks.value?.find(item => item.id === editing.value?.id) ?? editing.value
}

async function toggle(task: Task) {
  if (task.operation_type && task.status === 'open') {
    completingTask.value = task
    completing.value = true
    return
  }
  const command = task.status === 'open' ? 'complete' : 'reopen'
  const { data } = await api.POST('/api/farms/{farm_id}/tasks/{task_id}/{command}', {
    params: { path: { farm_id: farm.value!.id, task_id: task.id, command } }
  })
  if (data) {
    toast.add({ title: t(`app.tasks.did.${command}`), color: 'success', icon: 'i-lucide-check' })
    await refresh()
  }
}

function canToggle(task: Task) {
  return task.allowed_actions.includes(task.status === 'open' ? 'complete_task' : 'reopen_task')
}

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
  <div class="mx-auto max-w-3xl">
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

    <div class="mt-6 flex flex-wrap items-center gap-2">
      <div
        class="flex rounded-full border border-default p-0.5 text-sm"
        role="tablist"
      >
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          type="button"
          role="tab"
          :aria-selected="status === tab.value"
          class="rounded-full px-3 py-1 font-medium transition-colors"
          :class="status === tab.value ? 'bg-elevated text-highlighted' : 'text-muted hover:text-highlighted'"
          @click="status = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
      <USelect
        v-model="assignee"
        :items="assigneeItems"
        size="sm"
        icon="i-lucide-user"
        class="w-44"
        :aria-label="t('app.tasks.fields.assignee')"
      />
      <USelect
        v-model="priority"
        :items="priorityItems"
        size="sm"
        icon="i-lucide-flag"
        class="w-36"
        :aria-label="t('app.tasks.fields.priority')"
      />
      <USelect
        v-model="operationType"
        :items="typeItems"
        size="sm"
        icon="i-lucide-tractor"
        class="w-44"
        :aria-label="t('app.operations.kind')"
      />
      <USelect
        v-model="due"
        :items="dueItems"
        size="sm"
        icon="i-lucide-calendar"
        class="w-40"
        :aria-label="t('app.tasks.fields.dueDate')"
      />
    </div>

    <ul
      v-if="tasks?.length"
      class="mt-6 divide-y divide-default rounded-lg border border-default"
    >
      <li
        v-for="task in tasks"
        :key="task.id"
        class="flex items-start gap-3 px-3 py-3 sm:px-4"
        data-testid="task-row"
      >
        <button
          type="button"
          class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors disabled:cursor-not-allowed disabled:opacity-40"
          :class="task.status === 'done'
            ? 'border-primary bg-primary text-inverted'
            : task.status === 'discarded' ? 'border-dashed border-accented text-dimmed' : 'border-accented hover:border-primary'"
          :disabled="task.status === 'discarded' || !canToggle(task)"
          :aria-label="task.status === 'open' ? t('app.tasks.actions.complete') : t('app.tasks.actions.reopen')"
          :aria-pressed="task.status === 'done'"
          data-testid="task-toggle"
          @click="toggle(task)"
        >
          <UIcon
            v-if="task.status === 'done'"
            name="i-lucide-check"
            class="size-4"
          />
          <UIcon
            v-else-if="task.status === 'discarded'"
            name="i-lucide-archive"
            class="size-3.5"
          />
        </button>

        <button
          type="button"
          class="min-w-0 flex-1 text-left"
          @click="openEditor(task)"
        >
          <span
            class="block font-medium"
            :class="task.status === 'open' ? 'text-highlighted' : 'text-muted line-through decoration-1'"
          >
            {{ task.title }}
          </span>
          <span class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
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
              <template v-if="isOverdue(task, today)">· {{ t('app.tasks.overdue') }}</template>
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
            <span
              v-if="task.description"
              class="flex items-center gap-1"
            >
              <UIcon
                name="i-lucide-align-left"
                class="size-3.5"
              />
            </span>
          </span>
        </button>
      </li>
    </ul>

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
