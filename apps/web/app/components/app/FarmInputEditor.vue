<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type FarmInput = Schemas['FarmInputOut']
type Kind = Schemas['FarmInputKind']
type Unit = Schemas['FarmInputUnit']
type Source = Schemas['ValueSource']

const props = defineProps<{
  farmId: string
  /** The input to edit; null creates a new one. */
  input: FarmInput | null
  canWrite: boolean
}>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ changed: [] }>()

const { t, te } = useI18n()
const api = useApi()
const toast = useToast()

const KINDS: Kind[] = ['fertiliser', 'seed', 'other']
const UNITS: Unit[] = ['t', 'm3', '100kg']
const SOURCES: Source[] = ['standard_value', 'lab_analysis', 'manufacturer']
const NUTRIENTS = ['total_n', 'available_n', 'p2o5', 'k2o'] as const
const NONE = '__none'

interface State {
  kind: Kind
  name: string
  note: string
  unit: Unit
  dry_matter_percent: number | null
  total_n: number | null
  available_n: number | null
  p2o5: number | null
  k2o: number | null
  value_source: Source | typeof NONE
  source_reference: string
  analysed_on: string
  catalogue_entry: string | null
  land_use_code: string | undefined
  variety: string
  thousand_kernel_weight_g: number | null
}

function initial(): State {
  const i = props.input
  return {
    kind: i?.kind ?? 'fertiliser',
    name: i?.name ?? '',
    note: i?.note ?? '',
    unit: i?.unit ?? 'm3',
    dry_matter_percent: i?.dry_matter_percent ?? null,
    total_n: i?.total_n ?? null,
    available_n: i?.available_n ?? null,
    p2o5: i?.p2o5 ?? null,
    k2o: i?.k2o ?? null,
    value_source: i?.value_source ?? NONE,
    source_reference: i?.source_reference ?? '',
    analysed_on: i?.analysed_on ?? '',
    catalogue_entry: i?.catalogue_entry ?? null,
    land_use_code: i?.land_use_code ?? undefined,
    variety: i?.variety ?? '',
    thousand_kernel_weight_g: i?.thousand_kernel_weight_g ?? null
  }
}

const state = reactive<State>(initial())
const errorCode = ref<string | null>(null)
const busy = ref(false)
const confirmingDelete = ref(false)

watch(open, (isOpen) => {
  if (!isOpen) return
  Object.assign(state, initial())
  errorCode.value = null
  confirmingDelete.value = false
})

const { data: catalogue } = useAsyncData(
  () => `farm-input-catalogue-${props.farmId}`,
  async () => (await api.GET('/api/farms/{farm_id}/farm-input-catalogue', {
    params: { path: { farm_id: props.farmId } }
  })).data ?? []
)
const { data: landUses } = useAsyncData(
  () => `land-uses-${props.farmId}`,
  async () => (await api.GET('/api/farms/{farm_id}/land-uses', {
    params: { path: { farm_id: props.farmId } }
  })).data ?? []
)

const catalogueItems = computed(() => (catalogue.value ?? []).map(e => ({ label: e.name, value: e.code })))
const landUseItems = computed(() => (landUses.value ?? []).map(l => ({ label: `${landUseLabel(l.name)} (${l.code})`, value: l.code })))
const kindItems = computed(() => KINDS.map(kind => ({ label: t(`app.farmInputs.kinds.${kind}`), value: kind })))
const unitItems = computed(() => UNITS.map(unit => ({ label: t(`app.farmInputs.units.${unit}`), value: unit })))
const sourceItems = computed(() => [
  { label: '–', value: NONE },
  ...SOURCES.map(source => ({ label: t(`app.farmInputs.sources.${source}`), value: source }))
])
const catalogueEntry = computed(() => (catalogue.value ?? []).find(e => e.code === state.catalogue_entry) ?? null)

/** Copies the entry's values; later edits change only this Farm's copy. */
function startFromCatalogue(code: string) {
  const entry = (catalogue.value ?? []).find(e => e.code === code)
  if (!entry) return
  Object.assign(state, {
    name: state.name || entry.name,
    unit: entry.unit,
    dry_matter_percent: entry.dry_matter_percent,
    total_n: entry.total_n,
    available_n: entry.available_n,
    p2o5: entry.p2o5,
    k2o: entry.k2o,
    value_source: 'standard_value',
    source_reference: entry.source,
    analysed_on: '',
    catalogue_entry: entry.code
  })
}

function numberOrNull(value: unknown): number | null {
  if (value === '' || value === null || value === undefined) return null
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(',', '.'))
  return Number.isNaN(parsed) ? null : parsed
}

function body() {
  const common = { name: state.name.trim(), note: state.note.trim() || null }
  if (state.kind === 'fertiliser') {
    return {
      ...common,
      unit: state.unit,
      dry_matter_percent: numberOrNull(state.dry_matter_percent),
      total_n: numberOrNull(state.total_n),
      available_n: numberOrNull(state.available_n),
      p2o5: numberOrNull(state.p2o5),
      k2o: numberOrNull(state.k2o),
      value_source: state.value_source === NONE ? null : state.value_source,
      source_reference: state.source_reference.trim() || null,
      analysed_on: state.value_source === 'lab_analysis' ? state.analysed_on || null : null,
      catalogue_entry: state.catalogue_entry
    }
  }
  if (state.kind === 'seed') {
    return {
      ...common,
      land_use_code: state.land_use_code ?? null,
      variety: state.variety.trim() || null,
      thousand_kernel_weight_g: numberOrNull(state.thousand_kernel_weight_g)
    }
  }
  return common
}

// Checked here too, so the farmer hears why before the server says no.
const problem = computed(() => {
  if (!state.name.trim()) return 'name_required'
  if (state.kind === 'seed' && !state.land_use_code) return 'land_use_required'
  if (state.kind !== 'fertiliser') return null
  const values = [state.dry_matter_percent, ...NUTRIENTS.map(n => state[n])].map(numberOrNull)
  if (values.some(v => v !== null && v < 0)) return 'negative'
  const dm = numberOrNull(state.dry_matter_percent)
  if (dm !== null && dm > 100) return 'percent'
  const total = numberOrNull(state.total_n)
  const available = numberOrNull(state.available_n)
  if (total !== null && available !== null && available > total) return 'available_above_total'
  if (values.some(v => v !== null) && state.value_source === NONE) return 'value_source_required'
  if (state.value_source === 'lab_analysis' && !state.analysed_on) return 'analysed_on_required'
  return null
})

function codeOf(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  return typeof detail === 'string' && te(`app.farmInputs.errors.${detail}`) ? detail : 'unknown'
}

async function save() {
  if (problem.value) return
  busy.value = true
  errorCode.value = null
  const path = { farm_id: props.farmId }
  const result = props.input
    ? await api.PUT('/api/farms/{farm_id}/farm-inputs/{input_id}', {
        params: { path: { ...path, input_id: props.input.id } },
        body: body()
      })
    : await api.POST('/api/farms/{farm_id}/farm-inputs', {
        params: { path },
        body: { ...body(), kind: state.kind }
      })
  busy.value = false
  if (!result.data) {
    errorCode.value = codeOf(result.error)
    return
  }
  toast.add({ title: t(props.input ? 'app.farmInputs.saved' : 'app.farmInputs.created'), color: 'success', icon: 'i-lucide-check' })
  open.value = false
  emit('changed')
}

async function command(name: 'archive' | 'restore') {
  if (!props.input) return
  busy.value = true
  const params = { path: { farm_id: props.farmId, input_id: props.input.id } }
  const { data, error } = name === 'archive'
    ? await api.POST('/api/farms/{farm_id}/farm-inputs/{input_id}/archive', { params })
    : await api.POST('/api/farms/{farm_id}/farm-inputs/{input_id}/restore', { params })
  busy.value = false
  if (!data) {
    errorCode.value = codeOf(error)
    return
  }
  toast.add({ title: t(`app.farmInputs.did.${name}`), color: 'success', icon: 'i-lucide-check' })
  open.value = false
  emit('changed')
}

async function remove() {
  if (!props.input) return
  busy.value = true
  const { response, error } = await api.DELETE('/api/farms/{farm_id}/farm-inputs/{input_id}', {
    params: { path: { farm_id: props.farmId, input_id: props.input.id } }
  })
  busy.value = false
  if (response.status !== 204) {
    errorCode.value = codeOf(error)
    confirmingDelete.value = false
    return
  }
  toast.add({ title: t('app.farmInputs.deleted'), color: 'neutral', icon: 'i-lucide-trash-2' })
  open.value = false
  emit('changed')
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="input ? input.name : t('app.farmInputs.newTitle')"
    :description="input ? t(`app.farmInputs.kinds.${input.kind}`) : t('app.farmInputs.newLead')"
    :ui="{ content: 'sm:max-w-2xl' }"
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
          :title="t('app.farmInputs.deleteTitle')"
          :description="t('app.farmInputs.deleteWarning')"
        />
        <div class="flex justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('app.tasks.cancel')"
            @click="confirmingDelete = false"
          />
          <UButton
            color="error"
            icon="i-lucide-trash-2"
            :label="t('app.farmInputs.deleteForever')"
            :loading="busy"
            data-testid="confirm-delete-input"
            @click="remove"
          />
        </div>
      </div>

      <form
        v-else
        id="farm-input-form"
        class="space-y-4"
        @submit.prevent="save"
      >
        <fieldset
          :disabled="!canWrite"
          class="space-y-4"
        >
          <div class="grid gap-4 sm:grid-cols-[12rem_1fr]">
            <UFormField :label="t('app.farmInputs.fields.kind')">
              <USelect
                v-model="state.kind"
                :items="kindItems"
                :disabled="input !== null"
                class="w-full"
                data-testid="input-kind"
              />
            </UFormField>
            <UFormField :label="t('app.farmInputs.fields.name')">
              <UInput
                v-model="state.name"
                class="w-full"
                data-testid="input-name"
              />
            </UFormField>
          </div>

          <template v-if="state.kind === 'fertiliser'">
            <UFormField
              v-if="!input && canWrite && catalogueItems.length"
              :label="t('app.farmInputs.fromCatalogue')"
              :help="t('app.farmInputs.fromCatalogueHelp')"
            >
              <USelectMenu
                :model-value="state.catalogue_entry ?? undefined"
                :items="catalogueItems"
                value-key="value"
                :placeholder="t('app.farmInputs.chooseEntry')"
                :search-input="{ placeholder: t('app.farmInputs.searchCatalogue') }"
                class="w-full"
                data-testid="input-catalogue"
                @update:model-value="(code: string) => startFromCatalogue(code)"
              />
            </UFormField>

            <div class="rounded-md border border-default p-3">
              <div class="grid gap-3 sm:grid-cols-3">
                <UFormField
                  :label="t('app.farmInputs.fields.unit')"
                  :help="state.unit === '100kg' ? t('app.farmInputs.percentHint') : undefined"
                >
                  <USelect
                    v-model="state.unit"
                    :items="unitItems"
                    class="w-full"
                    data-testid="input-unit"
                  />
                </UFormField>
                <UFormField :label="t('app.farmInputs.fields.dry_matter_percent')">
                  <UInput
                    v-model="state.dry_matter_percent"
                    type="number"
                    inputmode="decimal"
                    min="0"
                    max="100"
                    step="0.1"
                    class="w-full"
                  />
                </UFormField>
              </div>
              <p class="mt-3 mb-1.5 text-sm font-medium text-default">
                {{ t('app.farmInputs.contentsPer', { unit: t(`app.farmInputs.unitsShort.${state.unit}`) }) }}
              </p>
              <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <UFormField
                  v-for="nutrient in NUTRIENTS"
                  :key="nutrient"
                  :label="t(`app.farmInputs.fields.${nutrient}`)"
                >
                  <UInput
                    v-model="state[nutrient]"
                    type="number"
                    inputmode="decimal"
                    min="0"
                    step="0.01"
                    class="w-full"
                    :data-testid="`input-${nutrient}`"
                  />
                </UFormField>
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-[14rem_1fr]">
              <UFormField
                :label="t('app.farmInputs.fields.value_source')"
                :help="t('app.farmInputs.sourceHelp')"
              >
                <USelect
                  v-model="state.value_source"
                  :items="sourceItems"
                  class="w-full"
                  data-testid="input-source"
                />
              </UFormField>
              <UFormField :label="t(`app.farmInputs.referenceLabel.${state.value_source === NONE ? 'standard_value' : state.value_source}`)">
                <UTextarea
                  v-model="state.source_reference"
                  :rows="1"
                  autoresize
                  class="w-full"
                  data-testid="input-reference"
                />
              </UFormField>
            </div>
            <UFormField
              v-if="state.value_source === 'lab_analysis'"
              :label="t('app.farmInputs.fields.analysed_on')"
              class="sm:w-56"
            >
              <UInput
                v-model="state.analysed_on"
                type="date"
                class="w-full"
                data-testid="input-analysed-on"
              />
            </UFormField>
            <p
              v-if="catalogueEntry"
              class="flex items-start gap-1.5 text-xs text-muted"
              data-testid="input-catalogue-note"
            >
              <UIcon
                name="i-lucide-book-open"
                class="mt-0.5 size-3.5 shrink-0"
              />
              {{ t('app.farmInputs.copiedFrom', { name: catalogueEntry.name }) }}
            </p>
          </template>

          <div
            v-else-if="state.kind === 'seed'"
            class="grid gap-3 sm:grid-cols-2"
          >
            <UFormField
              :label="t('app.farmInputs.fields.land_use')"
              class="sm:col-span-2"
            >
              <USelectMenu
                v-model="state.land_use_code"
                :items="landUseItems"
                value-key="value"
                :search-input="{ placeholder: t('app.farmInputs.searchLandUse') }"
                class="w-full"
                data-testid="input-land-use"
              />
            </UFormField>
            <UFormField :label="t('app.farmInputs.fields.variety')">
              <UInput
                v-model="state.variety"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('app.farmInputs.fields.thousand_kernel_weight_g')">
              <UInput
                v-model="state.thousand_kernel_weight_g"
                type="number"
                inputmode="decimal"
                min="0"
                step="0.1"
                class="w-full"
              />
            </UFormField>
          </div>

          <UFormField :label="t('app.details.fields.note')">
            <UTextarea
              v-model="state.note"
              :rows="1"
              autoresize
              class="w-full"
            />
          </UFormField>
        </fieldset>

        <UAlert
          v-if="input?.archived_at"
          color="neutral"
          variant="subtle"
          icon="i-lucide-archive"
          :description="t('app.farmInputs.archivedHint')"
        />
        <UAlert
          v-if="(problem && canWrite && state.name) || errorCode"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :description="t(`app.farmInputs.errors.${errorCode ?? problem}`)"
          data-testid="input-problem"
        />
      </form>
    </template>

    <template
      v-if="!confirmingDelete && canWrite"
      #footer
    >
      <div class="flex w-full flex-wrap items-center gap-2">
        <template v-if="input">
          <UButton
            v-if="input.archived_at"
            icon="i-lucide-archive-restore"
            color="neutral"
            variant="soft"
            :label="t('app.farmInputs.restore')"
            :loading="busy"
            @click="command('restore')"
          />
          <UButton
            v-else
            icon="i-lucide-archive"
            color="neutral"
            variant="ghost"
            :label="t('app.farmInputs.archive')"
            :loading="busy"
            data-testid="archive-input"
            @click="command('archive')"
          />
          <UTooltip
            :text="input.in_use ? t('app.farmInputs.inUseHint') : t('app.farmInputs.delete')"
          >
            <UButton
              icon="i-lucide-trash-2"
              color="error"
              variant="ghost"
              :disabled="input.in_use"
              :aria-label="t('app.farmInputs.delete')"
              data-testid="delete-input"
              @click="confirmingDelete = true"
            />
          </UTooltip>
        </template>
        <UButton
          type="submit"
          form="farm-input-form"
          class="ml-auto"
          :loading="busy"
          :disabled="problem !== null"
          :label="input ? t('app.tasks.save') : t('app.farmInputs.create')"
          data-testid="save-input"
        />
      </div>
    </template>
  </UModal>
</template>
