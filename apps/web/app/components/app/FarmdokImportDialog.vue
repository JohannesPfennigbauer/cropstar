<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type Problem = Schemas['ImportProblem']
// As the client returns it (its GeoJSON positions are looser than the schema's tuples).
type Preview = NonNullable<Awaited<ReturnType<typeof requestPreview>>['data']>

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ imported: [year: number] }>()

const ERROR_CODES = [
  'forbidden_for_role',
  'harvest_year_locked',
  'harvest_year_not_empty',
  'unknown_crops',
  'invalid_reference_year',
  'invalid_crop_assignments',
  'upload_too_large'
]
const MATCH_COLORS = { plot: '#22c55e', area: '#14b8a6', field: '#f59e0b', none: '#94a3b8' } as const

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { farm } = useAuth()
const { hectares } = useFormat()

// Without `multiple`, the file picker holds one file.
const file = ref<File | null>(null)
const preview = shallowRef<Preview | null>(null)
const referenceYear = ref<number | null>(null)
const crops = ref<Record<string, string>>({})
const problems = ref<Problem[]>([])
const errorCode = ref<string | null>(null)
const busy = ref(false)

function reset() {
  preview.value = null
  referenceYear.value = null
  crops.value = {}
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

const { data: landUses } = useAsyncData(
  () => `land-uses-${farm.value?.id}`,
  async () => {
    if (!farm.value) return []
    return (await api.GET('/api/farms/{farm_id}/land-uses', { params: { path: { farm_id: farm.value.id } } })).data ?? []
  }
)
const landUseItems = computed(() => (landUses.value ?? []).map(l => ({ label: `${landUseLabel(l.name)} (${l.code})`, value: l.code })))

function formData(): FormData {
  const data = new FormData()
  if (file.value) data.append('file', file.value, file.value.name)
  if (referenceYear.value !== null) data.append('reference_year', String(referenceYear.value))
  if (Object.keys(crops.value).length) data.append('crop_assignments', JSON.stringify(crops.value))
  return data
}

function requestPreview(farmId: string) {
  return api.POST('/api/farms/{farm_id}/imports/farmdok-field-list/preview', {
    params: { path: { farm_id: farmId } },
    body: { file: '' },
    bodySerializer: formData
  })
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
  const { data, error } = await requestPreview(farm.value.id)
  busy.value = false
  if (!data) return fail(error)
  preview.value = data
  referenceYear.value = data.reference_year
}

function chooseYear(year: number) {
  referenceYear.value = year
  showPreview()
}

function assignCrop(name: string, code: string) {
  crops.value = { ...crops.value, [name]: code }
  showPreview()
}

async function confirm() {
  if (!farm.value) return
  busy.value = true
  const { data, error } = await api.POST('/api/farms/{farm_id}/imports/farmdok-field-list', {
    params: { path: { farm_id: farm.value.id } },
    body: { file: '' },
    bodySerializer: formData
  })
  busy.value = false
  if (!data) return fail(error)
  open.value = false
  toast.add({
    title: t('app.farmdokImport.done', { year: data.harvest_year }),
    description: t('app.farmdokImport.doneDetail', { fields: data.field_count, plots: data.plot_count }),
    color: 'success',
    icon: 'i-lucide-check'
  })
  emit('imported', data.harvest_year)
}

function problemText(problem: Problem): string {
  return t(`app.farmdokImport.problems.${problem.code}`, { row: problem.row ?? '', detail: problem.detail ?? '' })
}

const yearItems = computed(() => (preview.value?.reference_years ?? []).map(year => ({ label: String(year), value: year })))

const matchLegend = computed(() => (['plot', 'area', 'field', 'none'] as const)
  .filter(match => (preview.value?.geometry_counts[match] ?? 0) > 0 && match !== 'none')
  .map(match => ({ label: t(`app.farmdokImport.match.${match}`), color: MATCH_COLORS[match] })))

const mapPlots = computed(() => ({
  type: 'FeatureCollection' as const,
  features: (preview.value?.plots.features ?? []).map(feature => ({
    ...feature,
    properties: { ...feature.properties, color: MATCH_COLORS[feature.properties.geometry_match] }
  }))
}))
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('app.farmdokImport.title')"
    :description="t('app.farmdokImport.lead')"
    :ui="{ content: preview ? 'sm:max-w-5xl' : 'sm:max-w-2xl' }"
  >
    <template #body>
      <div
        v-if="preview"
        class="space-y-4"
        data-testid="farmdok-preview"
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
              {{ t('app.areaUpload.plots') }}
            </dt>
            <dd class="tabular-nums text-highlighted">
              {{ t('app.areaUpload.count', { n: preview.plots.features.length, area: hectares(preview.plot_area_ha) }) }}
            </dd>
          </div>
          <div class="col-span-2">
            <dt class="text-muted">
              {{ t('app.farmdokImport.referenceYear') }}
            </dt>
            <dd>
              <USelect
                v-if="yearItems.length"
                :model-value="referenceYear ?? undefined"
                :items="yearItems"
                :disabled="busy"
                class="w-32"
                data-testid="farmdok-reference-year"
                @update:model-value="chooseYear"
              />
              <span
                v-else
                class="text-muted"
              >{{ t('app.farmdokImport.noReference') }}</span>
            </dd>
          </div>
        </dl>

        <p
          class="text-sm text-toned"
          data-testid="farmdok-geometry-counts"
        >
          {{ t('app.farmdokImport.geometrySummary', {
            plot: preview.geometry_counts.plot ?? 0,
            area: preview.geometry_counts.area ?? 0,
            field: preview.geometry_counts.field ?? 0,
            none: preview.geometry_counts.none ?? 0
          }) }}
        </p>

        <UAlert
          v-for="blocker in preview.blockers.filter(b => b !== 'unknown_crops')"
          :key="blocker"
          color="warning"
          variant="subtle"
          icon="i-lucide-lock"
          :description="t(`app.farmdokImport.blockers.${blocker}`, { year: preview.harvest_year })"
        />

        <div
          v-if="preview.unknown_crops.length"
          class="rounded-md border border-default p-3"
          data-testid="farmdok-unknown-crops"
        >
          <p class="text-sm font-medium text-highlighted">
            {{ t('app.farmdokImport.unknownCrops') }}
          </p>
          <p class="mt-0.5 text-xs text-muted">
            {{ t('app.farmdokImport.unknownCropsLead') }}
          </p>
          <ul class="mt-3 space-y-2">
            <li
              v-for="crop in preview.unknown_crops"
              :key="crop.name"
              class="flex flex-col gap-2 sm:flex-row sm:items-center"
            >
              <span class="min-w-0 flex-1 text-sm">
                {{ crop.name }}
                <span class="text-muted">· {{ t('app.plots.plotCount', crop.plot_count) }}</span>
              </span>
              <USelectMenu
                :model-value="crops[crop.name]"
                :items="landUseItems"
                value-key="value"
                :placeholder="t('app.farmdokImport.chooseLandUse')"
                :search-input="{ placeholder: t('app.farmInputs.searchLandUse') }"
                :disabled="busy"
                class="w-full sm:w-80"
                :data-testid="`farmdok-crop-${crop.name}`"
                @update:model-value="(code: string) => assignCrop(crop.name, code)"
              />
            </li>
          </ul>
        </div>

        <div class="h-72 overflow-hidden rounded-md border border-default">
          <AppFarmMap
            :plots="mapPlots"
            :legend-items="matchLegend"
          />
        </div>
        <p class="flex items-start gap-1.5 text-xs text-muted">
          <UIcon
            name="i-lucide-info"
            class="mt-0.5 size-3.5 shrink-0"
          />
          {{ t('app.farmdokImport.provisionalHint') }}
        </p>
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
          :label="t('app.farmdokImport.file')"
          :description="t('app.farmdokImport.fileHint')"
          class="w-full"
          data-testid="farmdok-file"
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
          :title="t('app.farmdokImport.invalid')"
          data-testid="farmdok-problems"
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
        :description="t(`app.farmdokImport.errors.${errorCode}`)"
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
            :label="t('app.farmdokImport.confirm')"
            data-testid="farmdok-confirm"
            @click="confirm"
          />
        </template>
        <UButton
          v-else
          :loading="busy"
          :disabled="!file"
          :label="t('app.areaUpload.preview')"
          data-testid="farmdok-preview-button"
          @click="showPreview"
        />
      </div>
    </template>
  </UModal>
</template>
