<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

definePageMeta({ layout: 'app' })

type FarmInput = Schemas['FarmInputOut']
type Kind = Schemas['FarmInputKind']

const KINDS: Kind[] = ['fertiliser', 'seed', 'other']

const { t } = useI18n()
const api = useApi()
const localePath = useLocalePath()
const { farm, membership } = useAuth()
const { decimal, day } = useFormat()

useSeoMeta({ title: () => t('app.farmInputs.title') })

const canWrite = computed(() => membership.value?.role === 'admin' || membership.value?.role === 'worker')
const showArchived = ref(false)

const { data: inputs, refresh } = await useAsyncData('farm-inputs', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/farm-inputs', {
    params: { path: { farm_id: farm.value.id } }
  })).data ?? []
}, { watch: [() => farm.value?.id] })

const archivedCount = computed(() => (inputs.value ?? []).filter(i => i.archived_at).length)
const byKind = computed(() => KINDS.map(kind => ({
  kind,
  items: (inputs.value ?? []).filter(i => i.kind === kind && (showArchived.value || !i.archived_at))
})))

const editing = ref<FarmInput | null>(null)
const editorOpen = ref(false)
function openEditor(input: FarmInput | null) {
  editing.value = input
  editorOpen.value = true
}

/** E.g. "je m³: 4,2 kg N (2,4 jahreswirksam) · 1,6 kg P₂O₅ · 5,5 kg K₂O · 7,5 % TM". */
function contents(input: FarmInput): string {
  if (!input.unit) return ''
  const parts: string[] = []
  if (input.total_n !== null) {
    const available = input.available_n !== null ? ` ${t('app.farmInputs.availableShort', { n: decimal(input.available_n) })}` : ''
    parts.push(`${decimal(input.total_n)} kg N${available}`)
  }
  else if (input.available_n !== null) {
    parts.push(t('app.farmInputs.availableOnly', { n: decimal(input.available_n) }))
  }
  if (input.p2o5 !== null) parts.push(`${decimal(input.p2o5)} kg P₂O₅`)
  if (input.k2o !== null) parts.push(`${decimal(input.k2o)} kg K₂O`)
  if (input.dry_matter_percent !== null) parts.push(`${decimal(input.dry_matter_percent)} % TM`)
  if (!parts.length) return ''
  return `${t('app.farmInputs.per', { unit: t(`app.farmInputs.unitsShort.${input.unit}`) })}: ${parts.join(' · ')}`
}

function source(input: FarmInput): string {
  if (!input.value_source) return ''
  const kind = t(`app.farmInputs.sources.${input.value_source}`)
  const when = input.analysed_on ? ` ${day(input.analysed_on)}` : ''
  return [`${kind}${when}`, input.source_reference].filter(Boolean).join(' · ')
}

function seedLine(input: FarmInput): string {
  return [
    input.land_use_name ? landUseLabel(input.land_use_name) : null,
    input.variety,
    input.thousand_kernel_weight_g !== null ? t('app.farmInputs.tkw', { g: decimal(input.thousand_kernel_weight_g) }) : null
  ].filter(Boolean).join(' · ')
}
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-6">
    <div>
      <ULink
        :to="localePath('/app/farm')"
        class="inline-flex items-center gap-1 text-sm text-muted hover:text-highlighted"
      >
        <UIcon
          name="i-lucide-arrow-left"
          class="size-4"
        />
        {{ t('app.farm.title') }}
      </ULink>
      <div class="mt-2 flex flex-wrap items-center justify-between gap-3">
        <h1 class="text-3xl font-semibold text-highlighted">
          {{ t('app.farmInputs.title') }}
        </h1>
        <UButton
          v-if="canWrite"
          icon="i-lucide-plus"
          :label="t('app.farmInputs.new')"
          data-testid="new-input"
          @click="openEditor(null)"
        />
      </div>
      <p class="mt-1 text-sm text-muted">
        {{ t('app.farmInputs.lead') }}
      </p>
    </div>

    <section
      v-for="group in byKind"
      :key="group.kind"
    >
      <h2 class="mb-2 text-lg font-semibold text-highlighted">
        {{ t(`app.farmInputs.kindsPlural.${group.kind}`) }}
      </h2>
      <ul
        v-if="group.items.length"
        class="divide-y divide-default rounded-lg border border-default"
      >
        <li
          v-for="input in group.items"
          :key="input.id"
        >
          <button
            type="button"
            class="flex w-full flex-col gap-0.5 p-3 text-left text-sm transition-colors hover:bg-elevated"
            :class="{ 'opacity-60': input.archived_at }"
            data-testid="input-row"
            @click="openEditor(input)"
          >
            <span class="flex items-center gap-2 font-medium text-highlighted">
              {{ input.name }}
              <UBadge
                v-if="input.archived_at"
                color="neutral"
                variant="subtle"
                size="sm"
              >
                {{ t('app.farmInputs.archived') }}
              </UBadge>
            </span>
            <span
              v-if="input.kind === 'fertiliser' && contents(input)"
              class="text-toned tabular-nums"
            >{{ contents(input) }}</span>
            <span
              v-if="input.kind === 'fertiliser' && source(input)"
              class="flex items-center gap-1 text-xs text-muted"
            >
              <UIcon
                name="i-lucide-book-open"
                class="size-3.5 shrink-0"
              />
              {{ source(input) }}
            </span>
            <span
              v-if="input.kind === 'seed'"
              class="text-toned"
            >{{ seedLine(input) }}</span>
            <span
              v-if="input.note"
              class="text-xs text-muted"
            >{{ input.note }}</span>
          </button>
        </li>
      </ul>
      <p
        v-else
        class="text-sm text-muted"
      >
        {{ t(`app.farmInputs.empty.${group.kind}`) }}
      </p>
    </section>

    <UButton
      v-if="archivedCount"
      color="neutral"
      variant="link"
      size="sm"
      :icon="showArchived ? 'i-lucide-eye-off' : 'i-lucide-archive'"
      :label="showArchived ? t('app.farmInputs.hideArchived') : t('app.farmInputs.showArchived', archivedCount)"
      @click="showArchived = !showArchived"
    />

    <AppFarmInputEditor
      v-if="farm"
      v-model:open="editorOpen"
      :farm-id="farm.id"
      :input="editing"
      :can-write="canWrite"
      @changed="refresh"
    />
  </div>
</template>
