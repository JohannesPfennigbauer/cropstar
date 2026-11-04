<script setup lang="ts">
import type { DetailField, OperationDetails } from '~/utils/operation-details'
import { DETAIL_FIELDS } from '~/utils/operation-details'

/** The structured form for one Operation's Planned or Actual Details. */
const details = defineModel<OperationDetails>({ required: true })
defineProps<{ size?: 'sm' | 'md' }>()

const { t, te } = useI18n()

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

function choiceItems(field: DetailField) {
  if (field.kind !== 'choice') return []
  return [
    { label: '–', value: NONE },
    ...field.options.map(option => ({ label: t(`app.details.values.${field.group}.${option}`), value: option }))
  ]
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
      :label="t(`app.details.fields.${field.key}`)"
      :size="size"
    >
      <USelect
        v-if="field.kind === 'choice'"
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
      :help="te(`app.details.noteHint.${details.type}`) ? t(`app.details.noteHint.${details.type}`) : undefined"
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
