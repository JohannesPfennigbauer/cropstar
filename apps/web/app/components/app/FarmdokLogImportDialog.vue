<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type Problem = Schemas['ImportProblem']
type Unresolved = Schemas['UnresolvedOut']
type Preview = Schemas['CropLogPreview']
type ProductAnswer = { farm_input_id: string } | { create: true } | { none: true }

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ imported: [year: number] }>()

const ERROR_CODES = [
  'forbidden_for_role',
  'harvest_year_locked',
  'already_imported',
  'unresolved',
  'invalid_resolutions',
  'upload_too_large'
]
const SKIP = '__skip'
const CREATE = '__create'
const NONE = '__none'
const PLOT_PROBLEMS = ['unknown_field', 'unknown_crop', 'no_matching_plot']

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { farm } = useAuth()
const { day } = useFormat()
const { summary } = useOperationDetails()

const file = ref<File | null>(null)
const preview = shallowRef<Preview | null>(null)
const activities = ref<Record<string, string | null>>({})
const products = ref<Record<string, ProductAnswer>>({})
const entries = ref<Record<string, string[] | null>>({})
const problems = ref<Problem[]>([])
const errorCode = ref<string | null>(null)
const busy = ref(false)

function reset() {
  preview.value = null
  activities.value = {}
  products.value = {}
  entries.value = {}
  problems.value = []
  errorCode.value = null
}

watch(open, (isOpen) => {
  if (isOpen) {
    file.value = null
    reset()
  }
})
watch(file, reset)

function formData(): FormData {
  const data = new FormData()
  if (file.value) data.append('file', file.value, file.value.name)
  data.append('resolutions', JSON.stringify({
    activities: activities.value,
    products: products.value,
    entries: entries.value
  }))
  return data
}

function fail(error: { detail?: unknown } | undefined) {
  const detail = error?.detail
  if (detail && typeof detail === 'object' && 'problems' in detail) {
    problems.value = (detail as Schemas['InvalidReport']).problems
    preview.value = null
    return
  }
  errorCode.value = typeof detail === 'string' && ERROR_CODES.includes(detail) ? detail : 'unknown'
}

async function showPreview() {
  if (!farm.value) return
  busy.value = true
  problems.value = []
  errorCode.value = null
  const { data, error } = await api.POST('/api/farms/{farm_id}/imports/farmdok-crop-log/preview', {
    params: { path: { farm_id: farm.value.id } },
    body: { file: '' },
    bodySerializer: formData
  })
  busy.value = false
  if (!data) return fail(error)
  preview.value = data
}

async function confirm() {
  if (!farm.value) return
  busy.value = true
  const { data, error } = await api.POST('/api/farms/{farm_id}/imports/farmdok-crop-log', {
    params: { path: { farm_id: farm.value.id } },
    body: { file: '' },
    bodySerializer: formData
  })
  busy.value = false
  if (!data) return fail(error)
  open.value = false
  toast.add({
    title: t('app.farmdokLog.done', { year: data.harvest_year }),
    description: t('app.farmdokLog.doneDetail', { tasks: data.task_count }),
    color: 'success',
    icon: 'i-lucide-check'
  })
  emit('imported', data.harvest_year)
}

function answerActivity(name: string, value: string) {
  activities.value = { ...activities.value, [name]: value === SKIP ? null : value }
  showPreview()
}

function answerProduct(name: string, value: string) {
  const answer: ProductAnswer = value === CREATE ? { create: true } : value === NONE ? { none: true } : { farm_input_id: value }
  products.value = { ...products.value, [name]: answer }
  showPreview()
}

function answerEntry(row: string, plotIds: string[] | null) {
  entries.value = { ...entries.value, [row]: plotIds }
  showPreview()
}

const pending = reactive<Record<string, string[]>>({})

const activityItems = computed(() => [
  ...(preview.value?.operation_types ?? []).map(code => ({ label: t(`app.operationTypes.${code}`), value: code })),
  { label: t('app.farmdokLog.skipActivity'), value: SKIP }
])

function productItems(item: Unresolved) {
  const inputs = (preview.value?.farm_inputs ?? []).filter(i => i.kind === item.input_kind && !i.archived)
  return [
    ...inputs.map(i => ({ label: i.name, value: i.id })),
    ...(item.can_create ? [{ label: t('app.farmdokLog.createInput', { name: item.key }), value: CREATE }] : []),
    { label: t('app.farmdokLog.withoutInput'), value: NONE }
  ]
}

const plotItems = computed(() => (preview.value?.plots ?? []).map(p => ({
  label: `${t('app.tasks.plotRef', { field: p.field_number, plot: p.number })} · ${landUseLabel(p.land_use_name)}`,
  value: p.id
})))

const groups = computed(() => {
  const all = preview.value?.unresolved ?? []
  return {
    activities: all.filter(u => u.problem === 'unknown_activity'),
    products: all.filter(u => u.problem === 'unknown_product' || u.problem === 'unit_mismatch'),
    entries: all.filter(u => PLOT_PROBLEMS.includes(u.problem))
  }
})

function entryLine(entry: Schemas['LogEntryOut']): string {
  return [
    day(entry.performed_on),
    entry.activity,
    t('app.farmdokLog.fields', { fields: entry.field_numbers.join(', ') }),
    entry.crop,
    entry.product
  ].filter(Boolean).join(' · ')
}

function problemText(problem: Problem): string {
  return t(`app.farmdokImport.problems.${problem.code}`, { row: problem.row ?? '', detail: problem.detail ?? '' })
}

function plotsLine(task: Schemas['PlannedTaskOut']): string {
  return task.plots.map(p => t('app.tasks.plotRef', { field: p.field_number, plot: p.number })).join(', ')
}

function detailsLine(task: Schemas['PlannedTaskOut']): string {
  const applied = task.farm_input_name
    ? { farm_input: { id: '', name: task.farm_input_name, kind: 'other' as const, archived: false }, nutrients: null }
    : null
  return summary(task.details, applied)
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('app.farmdokLog.title')"
    :description="t('app.farmdokLog.lead')"
    :ui="{ content: preview ? 'sm:max-w-4xl' : 'sm:max-w-2xl' }"
  >
    <template #body>
      <div
        v-if="preview"
        class="space-y-4"
        data-testid="farmdok-log-preview"
      >
        <dl class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <dt class="text-muted">
              {{ t('app.areaUpload.harvestYear') }}
            </dt>
            <dd class="font-semibold text-highlighted">
              {{ preview.harvest_year }}
            </dd>
          </div>
          <div>
            <dt class="text-muted">
              {{ t('app.farmdokLog.entries') }}
            </dt>
            <dd class="tabular-nums text-highlighted">
              {{ preview.entry_count }}
            </dd>
          </div>
          <div>
            <dt class="text-muted">
              {{ t('app.farmdokLog.tasks') }}
            </dt>
            <dd
              class="tabular-nums text-highlighted"
              data-testid="farmdok-log-task-count"
            >
              {{ t('app.farmdokLog.taskCount', { tasks: preview.tasks.length, operations: preview.operation_count }) }}
            </dd>
          </div>
          <div>
            <dt class="text-muted">
              {{ t('app.farmdokLog.skipped') }}
            </dt>
            <dd class="tabular-nums text-highlighted">
              {{ preview.skipped_rows.length }}
            </dd>
          </div>
        </dl>

        <UAlert
          v-for="blocker in preview.blockers.filter(b => b !== 'unresolved')"
          :key="blocker"
          color="warning"
          variant="subtle"
          icon="i-lucide-lock"
          :description="t(`app.farmdokLog.blockers.${blocker}`, { year: preview.harvest_year })"
        />

        <section
          v-if="preview.unresolved.length"
          class="space-y-4 rounded-md border border-default p-3"
          data-testid="farmdok-log-unresolved"
        >
          <div>
            <p class="text-sm font-medium text-highlighted">
              {{ t('app.farmdokLog.unresolvedTitle', preview.unresolved.length) }}
            </p>
            <p class="mt-0.5 text-xs text-muted">
              {{ t('app.farmdokLog.unresolvedLead') }}
            </p>
          </div>

          <div
            v-for="item in groups.activities"
            :key="`a-${item.key}`"
            class="flex flex-col gap-2 sm:flex-row sm:items-center"
          >
            <span class="min-w-0 flex-1 text-sm">
              {{ t('app.farmdokLog.unknownActivity', { name: item.key }) }}
              <span class="text-muted">· {{ t('app.farmdokLog.entryCount', item.entries.length) }}</span>
            </span>
            <USelect
              :items="activityItems"
              :placeholder="t('app.farmdokLog.chooseType')"
              :disabled="busy"
              class="w-full sm:w-72"
              :data-testid="`farmdok-activity-${item.key}`"
              @update:model-value="(value: string) => answerActivity(item.key, value)"
            />
          </div>

          <div
            v-for="item in groups.products"
            :key="`p-${item.key}`"
            class="flex flex-col gap-2 sm:flex-row sm:items-center"
          >
            <span class="min-w-0 flex-1 text-sm">
              {{ t(`app.farmdokLog.${item.problem === 'unit_mismatch' ? 'unitMismatch' : 'unknownProduct'}`, { name: item.key }) }}
              <span class="text-muted">· {{ t('app.farmdokLog.entryCount', item.entries.length) }}</span>
            </span>
            <USelect
              :items="productItems(item)"
              :placeholder="t('app.farmdokLog.chooseInput')"
              :disabled="busy"
              class="w-full sm:w-72"
              :data-testid="`farmdok-product-${item.key}`"
              @update:model-value="(value: string) => answerProduct(item.key, value)"
            />
          </div>

          <div
            v-for="item in groups.entries"
            :key="`e-${item.key}`"
            class="space-y-2 border-t border-default pt-3"
            :data-testid="`farmdok-entry-${item.key}`"
          >
            <p class="text-sm">
              <span class="font-medium text-highlighted">{{ t(`app.farmdokLog.problems.${item.problem}`) }}</span>
              <span class="block text-xs text-muted">{{ entryLine(item.entries[0]!) }}</span>
            </p>
            <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
              <USelectMenu
                v-model="pending[item.key]"
                :items="plotItems"
                value-key="value"
                multiple
                :placeholder="t('app.farmdokLog.choosePlots')"
                :search-input="{ placeholder: t('app.tasks.searchAreas') }"
                class="w-full sm:flex-1"
                :data-testid="`farmdok-plots-${item.key}`"
              />
              <UButton
                size="sm"
                :disabled="busy || !pending[item.key]?.length"
                :label="t('app.farmdokLog.assign')"
                :data-testid="`farmdok-assign-${item.key}`"
                @click="answerEntry(item.key, pending[item.key] ?? [])"
              />
              <UButton
                size="sm"
                color="neutral"
                variant="ghost"
                :disabled="busy"
                :label="t('app.farmdokLog.skipEntry')"
                :data-testid="`farmdok-skip-${item.key}`"
                @click="answerEntry(item.key, null)"
              />
            </div>
          </div>
        </section>

        <section v-if="preview.tasks.length">
          <h3 class="mb-1.5 text-sm font-semibold text-highlighted">
            {{ t('app.farmdokLog.planned') }}
          </h3>
          <p
            v-if="preview.new_inputs.length"
            class="mb-2 text-xs text-muted"
          >
            {{ t('app.farmdokLog.newInputs', { names: preview.new_inputs.join(', ') }) }}
          </p>
          <ul class="max-h-72 divide-y divide-default overflow-y-auto rounded-md border border-default text-sm">
            <li
              v-for="task in preview.tasks"
              :key="task.row"
              class="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:items-baseline sm:gap-3"
              data-testid="farmdok-log-task"
            >
              <span class="w-24 shrink-0 tabular-nums text-muted">{{ day(task.performed_on) }}</span>
              <span class="min-w-0 flex-1">
                <span class="font-medium text-highlighted">{{ task.title }}</span>
                <span class="text-muted"> · {{ t(`app.operationTypes.${task.operation_type}`) }}</span>
                <span class="block text-xs text-toned">{{ detailsLine(task) }}</span>
              </span>
              <span class="shrink-0 text-xs text-muted">{{ plotsLine(task) }}</span>
            </li>
          </ul>
        </section>
      </div>

      <div
        v-else
        class="space-y-4"
      >
        <UFileUpload
          v-model="file"
          accept=".xls"
          layout="list"
          icon="i-lucide-file-spreadsheet"
          :label="t('app.farmdokLog.file')"
          :description="t('app.farmdokLog.fileHint')"
          class="w-full"
          data-testid="farmdok-log-file"
        />
        <p class="flex items-center gap-1.5 text-xs text-dimmed">
          <UIcon
            name="i-lucide-shield-check"
            class="size-3.5 shrink-0"
          />
          {{ t('app.areaUpload.privacy') }}
        </p>
        <UAlert
          v-if="problems.length"
          color="error"
          variant="subtle"
          icon="i-lucide-file-x"
          :title="t('app.farmdokLog.invalid')"
        >
          <template #description>
            <ul class="list-disc space-y-0.5 pl-4">
              <li
                v-for="(problem, index) in problems"
                :key="index"
              >
                {{ problemText(problem) }}
              </li>
            </ul>
          </template>
        </UAlert>
      </div>

      <UAlert
        v-if="errorCode"
        class="mt-4"
        color="error"
        variant="subtle"
        :description="t(`app.farmdokLog.errors.${errorCode}`)"
      />
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <template v-if="preview">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('app.farmdokImport.back')"
            @click="reset"
          />
          <UButton
            :loading="busy"
            :disabled="preview.blockers.length > 0"
            :label="t('app.farmdokLog.confirm')"
            data-testid="farmdok-log-confirm"
            @click="confirm"
          />
        </template>
        <UButton
          v-else
          :loading="busy"
          :disabled="!file"
          :label="t('app.areaUpload.preview')"
          data-testid="farmdok-log-preview-button"
          @click="showPreview"
        />
      </div>
    </template>
  </UModal>
</template>
