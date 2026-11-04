<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'
import type { OperationDetails, OperationTypeCode } from '~/utils/operation-details'

type Task = Schemas['TaskOut']

const props = defineProps<{
  farmId: string
  task: Task
  /** Operations to tick at the start; all Open ones when omitted. */
  only?: string[]
}>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()

interface Row { id: string, label: string, color: string, checked: boolean, actual: OperationDetails, date: string }
const rows = ref<Row[]>([])
const busy = ref(false)

watch(open, (isOpen) => {
  if (!isOpen) return
  const today = todayIso()
  rows.value = props.task.operations
    .filter(o => o.status === 'open')
    .map(o => ({
      id: o.id,
      label: `${t('app.tasks.plotRef', { field: o.plot.field_number, plot: o.plot.number })} · ${landUseLabel(o.plot.land_use_name)}`,
      color: landUseColor(o.plot.land_use_category),
      checked: !props.only || props.only.includes(o.id),
      // A draft from an earlier, reopened completion wins over the plan.
      actual: structuredClone(toRaw(o.actual_details ?? o.planned_details))
        ?? emptyDetails(props.task.operation_type as OperationTypeCode),
      date: o.performed_on ?? today
    }))
}, { immediate: true })

const chosen = computed(() => rows.value.filter(r => r.checked))
const problem = computed(() => chosen.value.map(r => detailsProblem(r.actual)).find(Boolean) ?? null)

async function submit() {
  busy.value = true
  for (const row of chosen.value) {
    const { error } = await api.POST('/api/farms/{farm_id}/tasks/{task_id}/operations/{operation_id}/{command}', {
      params: { path: { farm_id: props.farmId, task_id: props.task.id, operation_id: row.id, command: 'complete' } },
      body: { actual_details: cleanDetails(row.actual), performed_on: row.date || null }
    })
    if (error) {
      busy.value = false
      toast.add({ title: t('app.errors.unknown'), color: 'error', icon: 'i-lucide-circle-alert' })
      emit('changed')
      return
    }
  }
  busy.value = false
  toast.add({ title: t('app.operations.recorded', chosen.value.length), color: 'success', icon: 'i-lucide-check' })
  open.value = false
  emit('changed')
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('app.operations.completeTitle', { task: task.title })"
    :description="t('app.operations.completeLead')"
  >
    <template #body>
      <ul class="space-y-4">
        <li
          v-for="row in rows"
          :key="row.id"
          class="rounded-lg border border-default p-3"
          data-testid="complete-row"
        >
          <UCheckbox v-model="row.checked">
            <template #label>
              <span class="flex items-center gap-2 font-medium text-highlighted">
                <span
                  class="size-2.5 rounded-sm"
                  :style="{ backgroundColor: row.color }"
                  aria-hidden="true"
                />
                {{ row.label }}
              </span>
            </template>
          </UCheckbox>
          <div
            v-if="row.checked"
            class="mt-3 space-y-3"
          >
            <UFormField
              :label="t('app.operations.performedOn')"
              class="sm:w-48"
            >
              <UInput
                v-model="row.date"
                type="date"
                class="w-full"
              />
            </UFormField>
            <fieldset>
              <legend class="mb-1.5 text-sm font-medium text-default">
                {{ t('app.operations.actual') }}
              </legend>
              <AppOperationDetailsForm
                v-model="row.actual"
                size="sm"
              />
            </fieldset>
          </div>
        </li>
      </ul>
      <UAlert
        v-if="problem"
        class="mt-4"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :description="t(`app.details.errors.${problem}`)"
      />
    </template>
    <template #footer>
      <UButton
        class="ml-auto"
        icon="i-lucide-check"
        :disabled="chosen.length === 0 || problem !== null"
        :loading="busy"
        :label="t('app.operations.record', chosen.length)"
        data-testid="record-operations"
        @click="submit"
      />
    </template>
  </UModal>
</template>
