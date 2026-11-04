<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

type Problem = Schemas['ExportProblem']
type AreaStatus = Schemas['AreaStatus']
type Decision = Schemas['AreaDecision']
// As the client returns it (its GeoJSON positions are looser than the schema's tuples).
type Preview = NonNullable<Awaited<ReturnType<typeof requestPreview>>['data']>
type Kind = 'plots' | 'fields'

interface Row {
  key: string
  kind: Kind
  label: string
  detail: string
  decision: Decision
}

interface CurrentArea {
  id: string
  label: string
  detail: string
}

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ uploaded: [year: number] }>()

const ERROR_CODES = [
  'forbidden_for_role',
  'harvest_year_locked',
  'undecided_areas',
  'removes_referenced_areas',
  'invalid_assignments',
  'upload_too_large'
]
const NEW = 'new'
const STATUS_ORDER: AreaStatus[] = ['undecided', 'changed', 'new', 'unchanged']
const STATUS_COLORS: Record<AreaStatus, string> = {
  undecided: '#a855f7',
  changed: '#f59e0b',
  new: '#22c55e',
  unchanged: '#94a3b8'
}
const STATUS_BADGES = {
  undecided: 'error',
  changed: 'warning',
  new: 'success',
  unchanged: 'neutral'
} as const
const REMOVED_COLOR = '#dc2626'

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const localePath = useLocalePath()
const { farm } = useAuth()
const { hectares } = useFormat()

const files = ref<File[] | null>(null)
const preview = shallowRef<Preview | null>(null)
// Only the Admin's own choices; everything else takes Cropstar's suggestion, if there is one.
const assignments = ref(new Map<string, string | null>())
const problems = ref<Problem[]>([])
const errorCode = ref<string | null>(null)
const busy = ref(false)
const refreshing = ref(false)
const showUnchanged = ref(false)
const hoveredKey = ref<string | null>(null)
let request = 0

function clearResult() {
  preview.value = null
  assignments.value = new Map()
  problems.value = []
  errorCode.value = null
  showUnchanged.value = false
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
  const chosen = [...assignments.value].map(([key, target]) => ({ key, target }))
  if (chosen.length) data.append('assignments', JSON.stringify(chosen))
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

// The files are sent again with every choice: the server keeps nothing between requests.
async function refresh() {
  if (!farm.value) return
  const mine = ++request
  refreshing.value = true
  errorCode.value = null
  const { data, error } = await requestPreview(farm.value.id)
  if (mine !== request) return
  refreshing.value = false
  if (data) preview.value = data
  else fail(error)
}

function choose(row: Row, value: string) {
  const target = value === NEW ? null : value
  const next = new Map(assignments.value)
  if (target !== null) {
    // An existing area can stay only one area; whoever had it has to be decided again.
    for (const [key, chosen] of next) if (chosen === target && key !== row.key) next.delete(key)
  }
  next.set(row.key, target)
  assignments.value = next
  refresh()
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
  // A first upload creates everything; only a re-upload has changes worth listing.
  const changes = data.created_count !== data.field_count + data.plot_count
  toast.add({
    title: t('app.areaUpload.done', { year: data.harvest_year }),
    description: [
      t('app.areaUpload.doneDetail', { fields: data.field_count, plots: data.plot_count }),
      changes
        ? t('app.areaUpload.doneChanges', {
            created: data.created_count,
            changed: data.changed_count,
            removed: data.removed_count
          })
        : ''
    ].join(' ').trim(),
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

function fieldLabel(number: number, name?: string | null): string {
  const label = t('app.plots.field', { number })
  return name ? `${label} · ${name}` : label
}

function plotLabel(fieldNumber: number, number: number): string {
  return t('app.tasks.plotRef', { field: fieldNumber, plot: number })
}

function areaDetail(landUse: string, area: number): string {
  return `${landUseLabel(landUse)} · ${hectares(area)}`
}

const current = computed(() => {
  const byKind: Record<Kind, Map<string, CurrentArea>> = { plots: new Map(), fields: new Map() }
  for (const { properties: p } of preview.value?.current_plots.features ?? []) {
    byKind.plots.set(p.id, {
      id: p.id,
      label: plotLabel(p.field_number, p.number),
      detail: areaDetail(p.land_use_name, p.declared_area_ha)
    })
  }
  for (const { properties: p } of preview.value?.current_fields.features ?? []) {
    byKind.fields.set(p.id, {
      id: p.id,
      label: fieldLabel(p.number, p.name),
      detail: areaDetail(p.land_use_name, p.declared_area_ha)
    })
  }
  return byKind
})

const rows = computed<Record<Kind, Row[]>>(() => {
  const plots = (preview.value?.plots.features ?? []).map(({ properties: p }) => ({
    key: p.id,
    kind: 'plots' as const,
    label: plotLabel(p.field_number, p.number),
    detail: areaDetail(p.land_use_name, p.declared_area_ha),
    decision: p.decision
  }))
  const fields = (preview.value?.fields.features ?? []).map(({ properties: p }) => ({
    key: p.id,
    kind: 'fields' as const,
    label: fieldLabel(p.number, p.name),
    detail: areaDetail(p.land_use_name, p.declared_area_ha),
    decision: p.decision
  }))
  const order = (row: Row) => STATUS_ORDER.indexOf(row.decision.status)
  return {
    plots: [...plots].sort((a, b) => order(a) - order(b)),
    fields: [...fields].sort((a, b) => order(a) - order(b))
  }
})

function visible(kind: Kind): Row[] {
  return showUnchanged.value ? rows.value[kind] : rows.value[kind].filter(r => r.decision.status !== 'unchanged')
}

const counts = computed(() => {
  const all = [...rows.value.plots, ...rows.value.fields]
  const by = (status: AreaStatus) => all.filter(r => r.decision.status === status).length
  return {
    undecided: by('undecided'),
    changed: by('changed'),
    new: by('new'),
    unchanged: by('unchanged'),
    removed: removed.value.length
  }
})

const removed = computed(() => {
  const list = [
    ...(preview.value?.current_fields.features ?? []).map(f => ({
      kind: 'fields' as Kind, id: f.id, tasks: f.properties.tasks, removed: f.properties.removed
    })),
    ...(preview.value?.current_plots.features ?? []).map(f => ({
      kind: 'plots' as Kind, id: f.id, tasks: f.properties.tasks, removed: f.properties.removed
    }))
  ]
  return list
    .filter(area => area.removed)
    .map(area => ({ ...current.value[area.kind].get(area.id)!, tasks: area.tasks }))
})

const blockedTasks = computed(() => {
  const seen = new Map<string, string>()
  for (const area of removed.value) for (const task of area.tasks) seen.set(task.id, task.title)
  return [...seen.values()]
})

function choiceItems(row: Row) {
  const candidateIds = new Set(row.decision.candidates.map(c => c.id))
  const overlapping = row.decision.candidates.map(candidate => ({
    label: `${current.value[row.kind].get(candidate.id)?.label ?? ''} · ${t('app.areaUpload.coverage', { percent: Math.round(candidate.coverage * 100) })}`,
    value: candidate.id
  }))
  const others = [...current.value[row.kind].values()]
    .filter(area => !candidateIds.has(area.id))
    .map(area => ({ label: area.label, value: area.id }))
  const groups = []
  if (overlapping.length) groups.push([{ type: 'label' as const, label: t('app.areaUpload.overlapping') }, ...overlapping])
  if (others.length) groups.push([{ type: 'label' as const, label: t('app.areaUpload.others') }, ...others])
  groups.push([{ label: t('app.areaUpload.newArea'), value: NEW }])
  return groups
}

function choice(row: Row): string | undefined {
  if (!row.decision.decided) return undefined
  return row.decision.target ?? NEW
}

function changeText(row: Row): string {
  return row.decision.changes.map(change => t(`app.areaUpload.changes.${change}`)).join(', ')
}

const statusLegend = computed(() => [
  ...STATUS_ORDER
    .filter(status => counts.value[status] > 0)
    .map(status => ({ label: t(`app.areaUpload.status.${status}`), color: STATUS_COLORS[status] })),
  ...(counts.value.removed ? [{ label: t('app.areaUpload.status.removed'), color: REMOVED_COLOR }] : [])
])

const mapPlots = computed(() => ({
  type: 'FeatureCollection' as const,
  features: (preview.value?.plots.features ?? []).map(feature => ({
    ...feature,
    properties: { ...feature.properties, color: STATUS_COLORS[feature.properties.decision.status] }
  }))
}))

const mapRemoved = computed(() => ({
  type: 'FeatureCollection' as const,
  features: [
    ...(preview.value?.current_fields.features ?? []),
    ...(preview.value?.current_plots.features ?? [])
  ].filter(feature => feature.properties.removed)
}))
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('app.areaUpload.title')"
    :description="preview ? t('app.areaUpload.assignLead') : t('app.areaUpload.lead')"
    :ui="{ content: preview ? 'sm:max-w-6xl' : 'sm:max-w-3xl' }"
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

        <div
          class="flex flex-wrap gap-1.5"
          data-testid="area-upload-counts"
        >
          <UBadge
            v-for="status in STATUS_ORDER.filter(s => counts[s] > 0)"
            :key="status"
            :color="STATUS_BADGES[status]"
            variant="subtle"
          >
            {{ t(`app.areaUpload.statusCount.${status}`, counts[status]) }}
          </UBadge>
          <UBadge
            v-if="counts.removed"
            color="error"
            variant="outline"
          >
            {{ t('app.areaUpload.statusCount.removed', counts.removed) }}
          </UBadge>
        </div>

        <template
          v-for="blocker in preview.blockers"
          :key="blocker"
        >
          <UAlert
            v-if="blocker === 'removes_referenced_areas'"
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t('app.areaUpload.blockers.removes_referenced_areas')"
            data-testid="area-upload-blocker"
          >
            <template #description>
              <p>{{ t('app.areaUpload.referencedHint') }}</p>
              <ul class="mt-1 list-disc pl-4">
                <li
                  v-for="title in blockedTasks"
                  :key="title"
                >
                  {{ title }}
                </li>
              </ul>
              <ULink
                :to="localePath('/app/tasks')"
                class="mt-1 inline-block text-sm underline"
              >
                {{ t('app.areaUpload.toTasks') }}
              </ULink>
            </template>
          </UAlert>
          <UAlert
            v-else
            :color="blocker === 'undecided_areas' ? 'info' : 'warning'"
            variant="subtle"
            :icon="blocker === 'undecided_areas' ? 'i-lucide-git-compare-arrows' : 'i-lucide-lock'"
            :description="t(`app.areaUpload.blockers.${blocker}`, { year: preview.harvest_year, n: counts.undecided })"
            data-testid="area-upload-blocker"
          />
        </template>

        <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div
            class="max-h-[28rem] space-y-4 overflow-y-auto pr-1 transition-opacity"
            :class="{ 'opacity-60': refreshing }"
            :aria-busy="refreshing"
          >
            <section
              v-for="kind in (['plots', 'fields'] as const)"
              :key="kind"
            >
              <h3 class="mb-1.5 text-sm font-semibold text-highlighted">
                {{ t(`app.areaUpload.${kind}`) }}
              </h3>
              <p
                v-if="!visible(kind).length"
                class="text-sm text-muted"
              >
                {{ t('app.areaUpload.allUnchanged') }}
              </p>
              <ul
                v-else
                class="divide-y divide-default rounded-md border border-default"
              >
                <li
                  v-for="row in visible(kind)"
                  :key="row.key"
                  class="flex flex-col gap-2 p-2.5 sm:flex-row sm:items-center"
                  :class="{ 'bg-elevated': hoveredKey === row.key }"
                  :data-testid="`area-row-${row.key}`"
                  @mouseenter="hoveredKey = row.kind === 'plots' ? row.key : null"
                  @mouseleave="hoveredKey = null"
                >
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <UBadge
                        :color="STATUS_BADGES[row.decision.status]"
                        variant="subtle"
                        size="sm"
                      >
                        {{ t(`app.areaUpload.status.${row.decision.status}`) }}
                      </UBadge>
                      <span class="truncate text-sm font-medium text-highlighted">{{ row.label }}</span>
                    </div>
                    <p class="mt-0.5 truncate text-xs text-muted">
                      {{ row.detail }}
                      <template v-if="row.decision.changes.length">
                        · {{ changeText(row) }}
                      </template>
                      <template v-if="row.decision.suggested && row.decision.target">
                        · {{ t('app.areaUpload.suggested') }}
                      </template>
                    </p>
                  </div>
                  <USelect
                    :model-value="choice(row)"
                    :items="choiceItems(row)"
                    :placeholder="t('app.areaUpload.choose')"
                    :disabled="busy"
                    class="w-full sm:w-64"
                    :aria-label="t('app.areaUpload.chooseFor', { area: row.label })"
                    :data-testid="`area-choice-${row.key}`"
                    @update:model-value="(value: string) => choose(row, value)"
                  />
                </li>
              </ul>
            </section>
            <UButton
              v-if="counts.unchanged"
              color="neutral"
              variant="link"
              size="sm"
              :icon="showUnchanged ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
              :label="showUnchanged ? t('app.areaUpload.hideUnchanged') : t('app.areaUpload.showUnchanged', counts.unchanged)"
              @click="showUnchanged = !showUnchanged"
            />
            <section v-if="removed.length">
              <h3 class="mb-1.5 text-sm font-semibold text-highlighted">
                {{ t('app.areaUpload.removedTitle') }}
              </h3>
              <ul
                class="divide-y divide-default rounded-md border border-error/40"
                data-testid="area-upload-removed"
              >
                <li
                  v-for="area in removed"
                  :key="area.id"
                  class="p-2.5 text-sm"
                >
                  <span class="font-medium text-highlighted">{{ area.label }}</span>
                  <span class="text-muted"> · {{ area.detail }}</span>
                  <p
                    v-if="area.tasks.length"
                    class="mt-0.5 flex items-center gap-1 text-xs text-warning"
                  >
                    <UIcon
                      name="i-lucide-triangle-alert"
                      class="size-3.5 shrink-0"
                    />
                    {{ t('app.areaUpload.referencedBy', { tasks: area.tasks.map(task => task.title).join(', ') }) }}
                  </p>
                </li>
              </ul>
            </section>
          </div>
          <div class="h-72 lg:h-auto lg:min-h-[28rem]">
            <AppFarmMap
              :plots="mapPlots"
              :fields="preview.fields"
              :removed="mapRemoved"
              :legend-items="statusLegend"
              :hovered-id="hoveredKey"
              @hover="(id: string | null) => hoveredKey = id"
            />
          </div>
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
            :disabled="preview.blockers.length > 0 || refreshing"
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
