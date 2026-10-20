<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

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

interface Row { id: string, label: string, color: string, checked: boolean, actual: string, date: string }
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
      actual: o.actual_details ?? o.planned_details ?? '',
      date: o.performed_on ?? today
    }))
}, { immediate: true })

const chosen = computed(() => rows.value.filter(r => r.checked))

async function submit() {
  busy.value = true
  for (const row of chosen.value) {
    const { error } = await api.POST('/api/farms/{farm_id}/tasks/{task_id}/operations/{operation_id}/{command}', {
      params: { path: { farm_id: props.farmId, task_id: props.task.id, operation_id: row.id, command: 'complete' } },
      body: { actual_details: row.actual || null, performed_on: row.date || null }
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
            class="mt-3 grid gap-3 sm:grid-cols-[1fr_10rem]"
          >
            <UFormField :label="t('app.operations.actual')">
              <UTextarea
                v-model="row.actual"
                :rows="2"
                autoresize
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('app.operations.performedOn')">
              <UInput
                v-model="row.date"
                type="date"
                class="w-full"
              />
            </UFormField>
          </div>
        </li>
      </ul>
    </template>
    <template #footer>
      <UButton
        class="ml-auto"
        icon="i-lucide-check"
        :disabled="chosen.length === 0"
        :loading="busy"
        :label="t('app.operations.record', chosen.length)"
        data-testid="record-operations"
        @click="submit"
      />
    </template>
  </UModal>
</template>
