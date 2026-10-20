<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Schemas } from '@cropstar/api-client'

type Task = Schemas['TaskOut']
type Member = Schemas['MemberOut']
type Command = 'complete' | 'reopen' | 'discard' | 'restore'

const props = defineProps<{
  farmId: string
  /** The Task to edit; null creates a new one. */
  task: Task | null
  members: Member[]
  /** Which Harvest Year's Fields and Plots to offer when the Task has none yet. */
  harvestYear: number | null
  /** Plots preselected for a new Task, e.g. when created from a Plot's page. */
  presetPlotIds?: string[]
}>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { membership } = useAuth()
const { moment } = useFormat()

const NOBODY = 'nobody'
const GENERAL = 'general'
const canRecordDone = computed(() => membership.value?.role !== 'advisor')

const schema = computed(() => z.object({
  title: z.string().trim().min(1, t('app.validation.required')).max(200),
  description: z.string().max(5000),
  due_date: z.string(),
  priority: z.enum(['none', 'low', 'normal', 'high']),
  assignee: z.string(),
  areas: z.array(z.string()),
  operation_type: z.string(),
  planned_details: z.string().max(5000),
  done: z.boolean()
}).refine(
  data => data.operation_type === GENERAL || data.areas.some(a => a.startsWith('plot:')),
  { message: t('app.operations.needsPlot'), path: ['areas'] }
))
type Schema = z.output<typeof schema.value>

function emptyState() {
  return {
    title: props.task?.title ?? '',
    description: props.task?.description ?? '',
    due_date: props.task?.due_date ?? '',
    priority: props.task?.priority ?? 'none' as Schemas['Priority'],
    assignee: props.task?.assignee?.id ?? NOBODY,
    areas: props.task
      ? [...props.task.fields.map(f => `field:${f.id}`), ...props.task.plots.map(p => `plot:${p.id}`)]
      : (props.presetPlotIds ?? []).map(id => `plot:${id}`),
    operation_type: props.task?.operation_type ?? GENERAL,
    planned_details: props.task?.planned_details ?? '',
    done: false
  }
}

// A Task's areas all come from one Harvest Year: the Task's own, else the one in view.
const areaYear = computed(() => props.task?.harvest_year ?? props.harvestYear)

const { data: areaOptions } = useAsyncData(
  () => `task-areas-${props.farmId}-${areaYear.value}`,
  async () => {
    if (areaYear.value === null) return null
    const params = { path: { farm_id: props.farmId }, query: { harvest_year: areaYear.value } }
    const [fields, plots] = await Promise.all([
      api.GET('/api/farms/{farm_id}/fields', { params }),
      api.GET('/api/farms/{farm_id}/plots', { params })
    ])
    return { fields: fields.data?.features ?? [], plots: plots.data?.features ?? [] }
  },
  { watch: [areaYear, () => props.farmId] }
)

const state = reactive(emptyState())
const isOperation = computed(() => state.operation_type !== GENERAL)

const { data: operationTypes } = useAsyncData(
  () => `operation-types-${props.farmId}`,
  async () => (await api.GET('/api/farms/{farm_id}/operation-types', {
    params: { path: { farm_id: props.farmId } }
  })).data ?? []
)
const typeItems = computed(() => [
  { label: t('app.operations.general'), value: GENERAL },
  ...(operationTypes.value ?? []).map(type => ({ label: t(`app.operationTypes.${type.code}`), value: type.code }))
])

// Operations concern Plots only, so Fields drop out of the picker for them.
watch(isOperation, (operation) => {
  if (operation) state.areas = state.areas.filter(a => a.startsWith('plot:'))
})

const completing = ref(false)
const completeOnly = ref<string[] | undefined>(undefined)
function openCompletion(only?: string[]) {
  completeOnly.value = only
  completing.value = true
}

const areaItems = computed(() => {
  if (!areaOptions.value) return []
  return [
    ...(isOperation.value ? [] : [{ type: 'label' as const, label: t('app.tasks.fieldsGroup'), value: 'group:fields' }]),
    ...(isOperation.value ? [] : areaOptions.value.fields).map(f => ({
      label: [t('app.plots.field', { number: f.properties.number }), f.properties.name].filter(Boolean).join(' · '),
      value: `field:${f.id}`
    })),
    { type: 'label' as const, label: t('app.tasks.plotsGroup'), value: 'group:plots' },
    ...areaOptions.value.plots.map(p => ({
      label: `${t('app.tasks.plotRef', { field: p.properties.field.number, plot: p.properties.number })} · ${landUseLabel(p.properties.land_use_name)}`,
      value: `plot:${p.id}`
    }))
  ]
})

const errorCode = ref<ApiErrorCode | 'invalid_assignee' | null>(null)
const busy = ref(false)
const confirmingDelete = ref(false)

watch(open, (isOpen) => {
  if (!isOpen) return
  Object.assign(state, emptyState())
  errorCode.value = null
  confirmingDelete.value = false
})

const priorityItems = computed(() => (['none', 'low', 'normal', 'high'] as const)
  .map(value => ({ label: t(`app.tasks.priority.${value}`), value })))

const assigneeItems = computed(() => [
  { label: t('app.tasks.nobody'), value: NOBODY },
  ...props.members.filter(m => m.assignable).map(m => ({ label: m.user.email, value: m.user.id }))
])

const allowed = computed(() => new Set(props.task?.allowed_actions ?? []))
const readOnly = computed(() => props.task !== null && !allowed.value.has('edit_task'))

function person(value: Schemas['PersonOut'] | null) {
  return value?.email ?? t('app.tasks.formerMember')
}

function codeOf(error: unknown) {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  return detail === 'invalid_assignee' ? 'invalid_assignee' : apiErrorCode(error)
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  busy.value = true
  errorCode.value = null
  const fields = {
    title: event.data.title,
    description: event.data.description || null,
    due_date: event.data.due_date || null,
    priority: event.data.priority,
    assignee_id: event.data.assignee === NOBODY ? null : event.data.assignee,
    field_ids: event.data.areas.filter(a => a.startsWith('field:')).map(a => a.slice(6)),
    plot_ids: event.data.areas.filter(a => a.startsWith('plot:')).map(a => a.slice(5)),
    planned_details: isOperation.value ? event.data.planned_details || null : null
  }
  const path = { farm_id: props.farmId }
  const result = props.task
    ? await api.PATCH('/api/farms/{farm_id}/tasks/{task_id}', {
        params: { path: { ...path, task_id: props.task.id } },
        body: fields
      })
    : await api.POST('/api/farms/{farm_id}/tasks', {
        params: { path },
        body: {
          ...fields,
          done: canRecordDone.value && event.data.done,
          operation_type: isOperation.value ? event.data.operation_type : null
        }
      })
  busy.value = false
  if (!result.data) {
    errorCode.value = codeOf(result.error)
    return
  }
  toast.add({ title: t(props.task ? 'app.tasks.saved' : 'app.tasks.created'), color: 'success', icon: 'i-lucide-check' })
  open.value = false
  emit('changed')
}

async function run(command: Command) {
  if (!props.task) return
  busy.value = true
  const { data, error } = await api.POST('/api/farms/{farm_id}/tasks/{task_id}/{command}', {
    params: { path: { farm_id: props.farmId, task_id: props.task.id, command } }
  })
  busy.value = false
  if (!data) {
    errorCode.value = codeOf(error)
    return
  }
  toast.add({ title: t(`app.tasks.did.${command}`), color: 'success', icon: 'i-lucide-check' })
  open.value = false
  emit('changed')
}

async function remove() {
  if (!props.task) return
  busy.value = true
  const { response, error } = await api.DELETE('/api/farms/{farm_id}/tasks/{task_id}', {
    params: { path: { farm_id: props.farmId, task_id: props.task.id } }
  })
  busy.value = false
  if (response.status !== 204) {
    errorCode.value = codeOf(error)
    return
  }
  toast.add({ title: t('app.tasks.deleted'), color: 'neutral', icon: 'i-lucide-trash-2' })
  open.value = false
  emit('changed')
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="task ? t('app.tasks.editTitle') : t('app.tasks.newTitle')"
    :description="task
      ? [t(`app.tasks.status.${task.status}`), task.operation_type && t(`app.operationTypes.${task.operation_type}`)].filter(Boolean).join(' · ')
      : t('app.tasks.newHint')"
  >
    <template #body>
      <div
        v-if="confirmingDelete"
        class="space-y-4"
      >
        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :title="t('app.tasks.deleteTitle')"
          :description="t('app.tasks.deleteWarning')"
        />
        <div class="flex flex-wrap justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('app.tasks.cancel')"
            @click="confirmingDelete = false"
          />
          <UButton
            v-if="allowed.has('discard_task')"
            color="neutral"
            variant="outline"
            icon="i-lucide-archive"
            :label="t('app.tasks.discardInstead')"
            :loading="busy"
            @click="run('discard')"
          />
          <UButton
            color="error"
            icon="i-lucide-trash-2"
            :label="t('app.tasks.deleteForever')"
            :loading="busy"
            data-testid="confirm-delete"
            @click="remove"
          />
        </div>
      </div>

      <UForm
        v-else
        id="task-form"
        :schema="schema"
        :state="state"
        :disabled="readOnly"
        class="space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          :label="t('app.tasks.fields.title')"
          name="title"
        >
          <UInput
            v-model="state.title"
            class="w-full"
            autofocus
          />
        </UFormField>
        <UFormField
          v-if="!task"
          :label="t('app.operations.kind')"
          :help="isOperation ? t('app.operations.kindHelp') : undefined"
          name="operation_type"
        >
          <USelect
            v-model="state.operation_type"
            :items="typeItems"
            class="w-full"
            data-testid="operation-type"
          />
        </UFormField>
        <UFormField
          :label="t('app.tasks.fields.description')"
          name="description"
        >
          <UTextarea
            v-model="state.description"
            :rows="3"
            autoresize
            class="w-full"
          />
        </UFormField>
        <div class="grid gap-4 sm:grid-cols-2">
          <UFormField
            :label="t('app.tasks.fields.dueDate')"
            name="due_date"
          >
            <UInput
              v-model="state.due_date"
              type="date"
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="t('app.tasks.fields.priority')"
            name="priority"
          >
            <USelect
              v-model="state.priority"
              :items="priorityItems"
              class="w-full"
            />
          </UFormField>
        </div>
        <UFormField
          v-if="areaYear !== null"
          :label="t('app.tasks.fields.areas')"
          :help="t('app.tasks.areasHelp', { year: areaYear })"
          name="areas"
        >
          <USelectMenu
            v-model="state.areas"
            :items="areaItems"
            value-key="value"
            multiple
            :search-input="{ placeholder: t('app.tasks.searchAreas') }"
            :placeholder="t('app.tasks.wholeFarm')"
            class="w-full"
            data-testid="task-areas"
          />
        </UFormField>
        <UFormField
          v-if="isOperation"
          :label="t('app.operations.planned')"
          :help="t('app.operations.plannedHelp')"
          name="planned_details"
        >
          <UTextarea
            v-model="state.planned_details"
            :rows="2"
            autoresize
            class="w-full"
          />
        </UFormField>
        <AppOperationList
          v-if="task?.operation_type"
          :farm-id="farmId"
          :task="task"
          @changed="emit('changed')"
          @complete="(id: string) => openCompletion([id])"
        />
        <UFormField
          :label="t('app.tasks.fields.assignee')"
          :help="t('app.tasks.assigneeHelp')"
          name="assignee"
        >
          <USelect
            v-model="state.assignee"
            :items="assigneeItems"
            class="w-full"
          />
        </UFormField>
        <UCheckbox
          v-if="!task && canRecordDone"
          v-model="state.done"
          :label="t('app.tasks.fields.done')"
          :description="t('app.tasks.doneHelp')"
        />

        <UAlert
          v-if="errorCode"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :description="t(`app.tasks.errors.${errorCode}`, t('app.errors.unknown'))"
        />

        <dl
          v-if="task"
          class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border-t border-default pt-3 text-xs text-muted"
        >
          <dt>{{ t('app.tasks.createdBy') }}</dt>
          <dd>{{ person(task.created_by) }} · {{ moment(task.created_at) }}</dd>
          <template v-if="task.completed_at">
            <dt>{{ t('app.tasks.completedBy') }}</dt>
            <dd>{{ person(task.completed_by) }} · {{ moment(task.completed_at) }}</dd>
          </template>
        </dl>
      </UForm>
    </template>

    <template
      v-if="!confirmingDelete"
      #footer
    >
      <div class="flex w-full flex-wrap items-center gap-2">
        <template v-if="task">
          <UButton
            v-if="allowed.has('complete_task')"
            icon="i-lucide-check"
            color="primary"
            variant="soft"
            :label="t('app.tasks.actions.complete')"
            :loading="busy"
            data-testid="complete-task"
            @click="task.operation_type ? openCompletion() : run('complete')"
          />
          <UButton
            v-if="allowed.has('reopen_task')"
            icon="i-lucide-rotate-ccw"
            color="neutral"
            variant="soft"
            :label="t('app.tasks.actions.reopen')"
            :loading="busy"
            @click="run('reopen')"
          />
          <UButton
            v-if="allowed.has('restore_task')"
            icon="i-lucide-archive-restore"
            color="neutral"
            variant="soft"
            :label="t('app.tasks.actions.restore')"
            :loading="busy"
            @click="run('restore')"
          />
          <UButton
            v-if="allowed.has('discard_task')"
            icon="i-lucide-archive"
            color="neutral"
            variant="ghost"
            :label="t('app.tasks.actions.discard')"
            :loading="busy"
            @click="run('discard')"
          />
          <UButton
            v-if="allowed.has('delete_task')"
            icon="i-lucide-trash-2"
            color="error"
            variant="ghost"
            :aria-label="t('app.tasks.actions.delete')"
            data-testid="delete-task"
            @click="confirmingDelete = true"
          />
        </template>
        <UButton
          v-if="!readOnly"
          type="submit"
          form="task-form"
          class="ml-auto"
          :loading="busy"
          :label="task ? t('app.tasks.save') : t('app.tasks.create')"
        />
      </div>
    </template>
  </UModal>
  <AppCompleteOperations
    v-if="task?.operation_type"
    v-model:open="completing"
    :farm-id="farmId"
    :task="task"
    :only="completeOnly"
    @changed="emit('changed')"
  />
</template>
