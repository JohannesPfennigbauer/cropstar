<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type Task = Schemas['TaskOut']
type Operation = Task['operations'][number]
type Command = 'reopen' | 'discard' | 'restore'

const props = defineProps<{ farmId: string, task: Task }>()
const emit = defineEmits<{ changed: [], complete: [operationId: string] }>()

const { t } = useI18n()
const api = useApi()
const { day } = useFormat()

const editing = ref<string | null>(null)
const draft = ref('')

function startEditing(operation: Operation) {
  editing.value = operation.id
  draft.value = operation.planned_details ?? ''
}

async function savePlan(operation: Operation) {
  await api.PATCH('/api/farms/{farm_id}/tasks/{task_id}/operations/{operation_id}', {
    params: { path: { farm_id: props.farmId, task_id: props.task.id, operation_id: operation.id } },
    body: { planned_details: draft.value || null }
  })
  editing.value = null
  emit('changed')
}

async function run(operation: Operation, command: Command) {
  await api.POST('/api/farms/{farm_id}/tasks/{task_id}/operations/{operation_id}/{command}', {
    params: { path: { farm_id: props.farmId, task_id: props.task.id, operation_id: operation.id, command } }
  })
  emit('changed')
}

const STATUS_ICON = { open: 'i-lucide-circle', done: 'i-lucide-circle-check', discarded: 'i-lucide-archive' } as const
</script>

<template>
  <div>
    <h3 class="text-sm font-semibold text-highlighted">
      {{ t('app.operations.title', { done: task.operations.filter(o => o.status === 'done').length, total: task.operations.filter(o => o.status !== 'discarded').length }) }}
    </h3>
    <ul class="mt-2 divide-y divide-default rounded-lg border border-default">
      <li
        v-for="operation in task.operations"
        :key="operation.id"
        class="p-3 text-sm"
        data-testid="operation-row"
      >
        <div class="flex items-center gap-2">
          <UIcon
            :name="STATUS_ICON[operation.status]"
            class="size-4 shrink-0"
            :class="operation.status === 'done' ? 'text-primary' : 'text-muted'"
          />
          <span
            class="size-2.5 shrink-0 rounded-sm"
            :style="{ backgroundColor: landUseColor(operation.plot.land_use_category) }"
            aria-hidden="true"
          />
          <span class="min-w-0 flex-1 truncate font-medium text-highlighted">
            {{ t('app.tasks.plotRef', { field: operation.plot.field_number, plot: operation.plot.number }) }} · {{ landUseLabel(operation.plot.land_use_name) }}
          </span>
          <UButton
            v-if="operation.allowed_actions.includes('complete_task')"
            size="xs"
            variant="soft"
            icon="i-lucide-check"
            :label="t('app.tasks.actions.complete')"
            @click="emit('complete', operation.id)"
          />
          <UButton
            v-if="operation.allowed_actions.includes('reopen_task')"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            :aria-label="t('app.tasks.actions.reopen')"
            @click="run(operation, 'reopen')"
          />
          <UButton
            v-if="operation.allowed_actions.includes('restore_task')"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-archive-restore"
            :aria-label="t('app.tasks.actions.restore')"
            @click="run(operation, 'restore')"
          />
          <UButton
            v-if="operation.allowed_actions.includes('discard_task')"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-archive"
            :aria-label="t('app.tasks.actions.discard')"
            @click="run(operation, 'discard')"
          />
        </div>

        <dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 pl-6 text-xs">
          <dt class="text-muted">
            {{ t('app.operations.planned') }}
          </dt>
          <dd>
            <div
              v-if="editing === operation.id"
              class="flex flex-col gap-2"
            >
              <UTextarea
                v-model="draft"
                :rows="2"
                autoresize
                size="sm"
                class="w-full"
              />
              <div class="flex gap-2">
                <UButton
                  size="xs"
                  :label="t('app.tasks.save')"
                  @click="savePlan(operation)"
                />
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  :label="t('app.tasks.cancel')"
                  @click="editing = null"
                />
              </div>
            </div>
            <span
              v-else
              class="inline-flex items-start gap-1 text-toned"
            >
              {{ operation.planned_details || '–' }}
              <UButton
                v-if="operation.status === 'open' && operation.allowed_actions.includes('edit_task')"
                size="xs"
                color="neutral"
                variant="link"
                icon="i-lucide-pencil"
                class="-my-1 p-0.5"
                :aria-label="t('app.operations.adjust')"
                @click="startEditing(operation)"
              />
            </span>
          </dd>
          <template v-if="operation.status === 'done'">
            <dt class="text-muted">
              {{ t('app.operations.actual') }}
            </dt>
            <dd class="text-highlighted">
              {{ operation.actual_details || '–' }}
              <span
                v-if="operation.performed_on"
                class="text-muted"
              >· {{ day(operation.performed_on) }}</span>
            </dd>
          </template>
        </dl>
      </li>
    </ul>
  </div>
</template>
