<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type Problem = Schemas['ExportProblem']
// As the client returns it (its GeoJSON positions are looser than the schema's tuples).
type Preview = NonNullable<Awaited<ReturnType<typeof requestPreview>>['data']>

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ uploaded: [year: number] }>()

const ERROR_CODES = ['forbidden_for_role', 'harvest_year_locked', 'harvest_year_not_empty', 'upload_too_large']

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { farm } = useAuth()
const { hectares } = useFormat()

const files = ref<File[] | null>(null)
const preview = shallowRef<Preview | null>(null)
const problems = ref<Problem[]>([])
const errorCode = ref<string | null>(null)
const busy = ref(false)

function clearResult() {
  preview.value = null
  problems.value = []
  errorCode.value = null
}

watch(open, (isOpen) => {
  if (isOpen) {
    files.value = null
    clearResult()
  }
})
watch(files, clearResult, { deep: true })

function formData(): FormData {
  const data = new FormData()
  for (const file of files.value ?? []) data.append('files', file, file.name)
  return data
}

function requestPreview(farmId: string) {
  return api.POST('/api/farms/{farm_id}/area-uploads/preview', {
    params: { path: { farm_id: farmId } },
    body: { files: [] },
    bodySerializer: formData
  })
}

function fail(error: { detail?: unknown } | undefined) {
  const detail = error?.detail
  if (detail && typeof detail === 'object' && 'problems' in detail) {
    problems.value = (detail as Schemas['InvalidExport']).problems
    return
  }
  errorCode.value = typeof detail === 'string' && ERROR_CODES.includes(detail) ? detail : 'unknown'
}

async function showPreview() {
  if (!farm.value) return
  clearResult()
  busy.value = true
  const { data, error } = await requestPreview(farm.value.id)
  busy.value = false
  if (data) preview.value = data
  else fail(error)
}

async function confirm() {
  if (!farm.value) return
  busy.value = true
  const { data, error } = await api.POST('/api/farms/{farm_id}/area-uploads', {
    params: { path: { farm_id: farm.value.id } },
    body: { files: [] },
    bodySerializer: formData
  })
  busy.value = false
  if (!data) {
    fail(error)
    return
  }
  open.value = false
  toast.add({
    title: t('app.areaUpload.done', { year: data.harvest_year }),
    description: t('app.areaUpload.doneDetail', { fields: data.field_count, plots: data.plot_count }),
    color: 'success',
    icon: 'i-lucide-check'
  })
  emit('uploaded', data.harvest_year)
}

function problemText(problem: Problem): string {
  const detail = problem.code === 'missing_set' && problem.detail
    ? t(`app.areaUpload.sets.${problem.detail}`)
    : problem.detail ?? ''
  return t(`app.areaUpload.problems.${problem.code}`, {
    file: problem.file ?? '',
    field: problem.field_number ?? '',
    plot: problem.plot_number ?? '',
    detail
  })
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('app.areaUpload.title')"
    :description="t('app.areaUpload.lead')"
    :ui="{ content: 'sm:max-w-3xl' }"
  >
    <template #body>
      <div
        v-if="preview"
        class="space-y-4"
        data-testid="area-upload-preview"
      >
        <dl class="grid grid-cols-3 gap-3 text-sm">
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
              {{ t('app.areaUpload.fields') }}
            </dt>
            <dd class="tabular-nums text-highlighted">
              {{ t('app.areaUpload.count', { n: preview.fields.features.length, area: hectares(preview.field_area_ha) }) }}
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
        </dl>
        <UAlert
          v-for="blocker in preview.blockers"
          :key="blocker"
          color="warning"
          variant="subtle"
          icon="i-lucide-lock"
          :description="t(`app.areaUpload.blockers.${blocker}`, { year: preview.harvest_year })"
        />
        <div class="h-72 overflow-hidden rounded-md border border-default">
          <AppFarmMap
            :plots="preview.plots"
            :fields="preview.fields"
          />
        </div>
      </div>

      <div
        v-else
        class="space-y-4"
      >
        <UFileUpload
          v-model="files"
          multiple
          accept=".shp,.shx,.dbf,.prj,.cpg,.zip"
          layout="list"
          icon="i-lucide-upload"
          :label="t('app.areaUpload.files')"
          :description="t('app.areaUpload.filesHint')"
          class="w-full"
          data-testid="area-upload-files"
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
          :title="t('app.areaUpload.invalid')"
          data-testid="area-upload-problems"
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
        :description="t(`app.areaUpload.errors.${errorCode}`)"
      />
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <template v-if="preview">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('app.areaUpload.back')"
            @click="clearResult"
          />
          <UButton
            :loading="busy"
            :disabled="preview.blockers.length > 0"
            :label="t('app.areaUpload.confirm')"
            data-testid="area-upload-confirm"
            @click="confirm"
          />
        </template>
        <UButton
          v-else
          :loading="busy"
          :disabled="!files?.length"
          :label="t('app.areaUpload.preview')"
          data-testid="area-upload-preview-button"
          @click="showPreview"
        />
      </div>
    </template>
  </UModal>
</template>
