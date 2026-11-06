<script setup lang="ts">
import type { DetailField, OperationDetails } from '~/utils/operation-details'
import { DETAIL_FIELDS, unitsFor } from '~/utils/operation-details'

/** The structured form for one Operation's Planned or Actual Details. */
const details = defineModel<OperationDetails>({ required: true })
defineProps<{ size?: 'sm' | 'md' }>()

const { t } = useI18n()
const api = useApi()
const { farm } = useAuth()

const { data: farmInputs } = useAsyncData(
  () => `farm-inputs-picker-${farm.value?.id}`,
  async () => {
    if (!farm.value) return []
    return (await api.GET('/api/farms/{farm_id}/farm-inputs', {
      params: { path: { farm_id: farm.value.id } }
    })).data ?? []
  },
  { watch: [() => farm.value?.id] }
)

// Reka's select cannot hold an empty value, so "nothing chosen" has its own.
const NONE = '__none'

const values = computed(() => details.value as Record<string, unknown>)
const fields = computed(() => DETAIL_FIELDS[details.value.type] ?? [])
const unitKeys = computed(() => new Set(fields.value.flatMap(f => f.kind === 'number' && f.unitKey ? [f.unitKey] : [])))
// Units are edited next to their amount, not as fields of their own.
const shown = computed(() => fields.value.filter(f => !unitKeys.value.has(f.key)))

function set(key: string, value: unknown) {
  details.value = { ...details.value, [key]: value } as OperationDetails
}

function setNumber(key: string, raw: unknown) {
  if (raw === '' || raw === null || raw === undefined) return set(key, undefined)
  const parsed = typeof raw === 'number' ? raw : Number(String(raw).replace(',', '.'))
  set(key, Number.isNaN(parsed) ? undefined : parsed)
}

const chosenInput = computed(() => {
  const id = values.value.farm_input_id
  return (farmInputs.value ?? []).find(i => i.id === id) ?? null
})

function choiceItems(field: DetailField) {
  if (field.kind !== 'choice') return []
  // Once a fertiliser is chosen, only units that fit its contents make sense.
  const fitting = field.key === 'unit' && details.value.type === 'fertilisation' ? unitsFor(chosenInput.value?.unit) : null
  return [
    { label: '–', value: NONE },
    ...field.options
      .filter(option => !fitting || fitting.includes(option))
      .map(option => ({ label: t(`app.details.values.${field.group}.${option}`), value: option }))
  ]
}

function inputItems(field: DetailField) {
  if (field.kind !== 'input') return []
  const current = values.value.farm_input_id
  // Archived inputs are not offered, but one already chosen stays visible.
  const offered = (farmInputs.value ?? []).filter(i => i.kind === field.inputKind && (!i.archived_at || i.id === current))
  return [
    { label: '–', value: NONE },
    ...offered.map(i => ({
      label: i.archived_at ? `${i.name} (${t('app.farmInputs.archived')})` : i.name,
      value: i.id
    }))
  ]
}

function setInput(value: string) {
  const id = value === NONE ? undefined : value
  const next: Record<string, unknown> = { ...details.value, farm_input_id: id }
  if (details.value.type === 'fertilisation') {
    // The model updates only after the parent re-renders, so look the input up directly.
    const fitting = unitsFor((farmInputs.value ?? []).find(i => i.id === id)?.unit)
    const unit = next.unit
    if (fitting && (typeof unit !== 'string' || !fitting.includes(unit))) next.unit = fitting[0]
  }
  details.value = next as OperationDetails
}

function choiceOf(key: string): string {
  const value = values.value[key]
  return typeof value === 'string' ? value : NONE
}

function unitField(field: DetailField): DetailField | undefined {
  return field.kind === 'number' && field.unitKey ? fields.value.find(f => f.key === field.unitKey) : undefined
}

function numberOf(key: string): string | number {
  const value = values.value[key]
  return typeof value === 'number' ? value : ''
}
</script>

<template>
  <div class="grid gap-3 sm:grid-cols-2">
    <UFormField
      v-for="field in shown"
      :key="field.key"
      :label="field.kind === 'input' ? t(`app.details.fields.input.${field.inputKind}`) : t(`app.details.fields.${field.key}`)"
      :help="field.kind === 'input' && !inputItems(field).slice(1).length ? t('app.details.noInputs') : undefined"
      :size="size"
    >
      <USelect
        v-if="field.kind === 'input'"
        :model-value="choiceOf(field.key)"
        :items="inputItems(field)"
        class="w-full"
        :data-testid="`details-${field.key}`"
        @update:model-value="setInput"
      />
      <USelect
        v-else-if="field.kind === 'choice'"
        :model-value="choiceOf(field.key)"
        :items="choiceItems(field)"
        class="w-full"
        :data-testid="`details-${field.key}`"
        @update:model-value="(value: string) => set(field.key, value === NONE ? undefined : value)"
      />
      <div
        v-else
        class="flex gap-2"
      >
        <UInput
          :model-value="numberOf(field.key)"
          type="number"
          inputmode="decimal"
          min="0"
          :max="field.max"
          :step="field.step"
          class="min-w-0 flex-1"
          :data-testid="`details-${field.key}`"
          @update:model-value="(value: unknown) => setNumber(field.key, value)"
        />
        <USelect
          v-if="unitField(field)"
          :model-value="choiceOf(unitField(field)!.key)"
          :items="choiceItems(unitField(field)!)"
          :aria-label="t('app.details.fields.unit')"
          class="w-32 shrink-0"
          :data-testid="`details-${unitField(field)!.key}`"
          @update:model-value="(value: string) => set(unitField(field)!.key, value === NONE ? undefined : value)"
        />
      </div>
    </UFormField>
    <UFormField
      :label="t('app.details.fields.note')"
      :size="size"
      class="sm:col-span-2"
    >
      <UTextarea
        :model-value="details.note ?? ''"
        :rows="1"
        autoresize
        class="w-full"
        data-testid="details-note"
        @update:model-value="(value: string) => set('note', value)"
      />
    </UFormField>
  </div>
</template>
