<script setup lang="ts">
const props = defineProps<{ farmId: string, canEdit: boolean }>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()

interface Draft { id: string | null, name: string, taskCount: number }

const { data: stages, refresh } = useAsyncData(
  () => `task-stages-${props.farmId}`,
  async () => (await api.GET('/api/farms/{farm_id}/task-stages', { params: { path: { farm_id: props.farmId } } })).data ?? []
)

const draft = ref<Draft[]>([])
watch(stages, (current) => {
  draft.value = (current ?? []).map(s => ({ id: s.id, name: s.name, taskCount: s.task_count }))
}, { immediate: true })

const busy = ref(false)
const dirty = computed(() => JSON.stringify(draft.value.map(d => [d.id, d.name.trim()]))
  !== JSON.stringify((stages.value ?? []).map(s => [s.id, s.name])))
const problem = computed(() => {
  const names = draft.value.map(d => d.name.trim().toLocaleLowerCase())
  if (names.some(n => !n)) return 'empty'
  if (new Set(names).size !== names.length) return 'duplicate'
  return null
})

function move(index: number, by: number) {
  const items = [...draft.value]
  const [item] = items.splice(index, 1)
  items.splice(index + by, 0, item!)
  draft.value = items
}

function remove(index: number) {
  draft.value = draft.value.filter((_, i) => i !== index)
}

function add() {
  draft.value = [...draft.value, { id: null, name: '', taskCount: 0 }]
}

async function save() {
  busy.value = true
  const { data } = await api.PUT('/api/farms/{farm_id}/task-stages', {
    params: { path: { farm_id: props.farmId } },
    body: { stages: draft.value.map(d => ({ id: d.id, name: d.name.trim() })) }
  })
  busy.value = false
  if (!data) {
    toast.add({ title: t('app.errors.unknown'), color: 'error', icon: 'i-lucide-circle-alert' })
    return
  }
  await refresh()
  toast.add({ title: t('app.tasks.stages.saved'), color: 'success', icon: 'i-lucide-check' })
}
</script>

<template>
  <div>
    <ol
      class="space-y-2"
      data-testid="task-stages"
    >
      <li
        v-for="(stage, index) in draft"
        :key="stage.id ?? `new-${index}`"
        class="flex items-center gap-2"
      >
        <span class="w-5 text-right text-sm tabular-nums text-muted">{{ index + 1 }}.</span>
        <UInput
          v-model="stage.name"
          :disabled="!canEdit"
          maxlength="60"
          class="min-w-0 flex-1"
          :aria-label="t('app.tasks.stages.name', { n: index + 1 })"
        />
        <template v-if="canEdit">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-arrow-up"
            :disabled="index === 0"
            :aria-label="t('app.tasks.stages.up')"
            @click="move(index, -1)"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-arrow-down"
            :disabled="index === draft.length - 1"
            :aria-label="t('app.tasks.stages.down')"
            @click="move(index, 1)"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-trash-2"
            :disabled="draft.length === 1"
            :aria-label="t('app.tasks.stages.remove')"
            :title="stage.taskCount ? t('app.tasks.stages.removeHint', stage.taskCount) : undefined"
            @click="remove(index)"
          />
        </template>
      </li>
      <li class="flex items-center gap-2 text-sm text-muted">
        <span class="w-5 text-right tabular-nums">{{ draft.length + 1 }}.</span>
        <span>{{ t('app.tasks.status.done') }}</span>
        <span class="text-xs text-dimmed">· {{ t('app.tasks.stages.doneFixed') }}</span>
      </li>
    </ol>
    <p
      v-if="problem && canEdit"
      class="mt-2 text-sm text-error"
    >
      {{ t(`app.tasks.stages.problems.${problem}`) }}
    </p>
    <div
      v-if="canEdit"
      class="mt-3 flex flex-wrap gap-2"
    >
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-plus"
        :label="t('app.tasks.stages.add')"
        :disabled="draft.length >= 10"
        @click="add"
      />
      <UButton
        size="sm"
        :loading="busy"
        :disabled="!dirty || problem !== null"
        :label="t('app.tasks.save')"
        data-testid="save-task-stages"
        @click="save"
      />
    </div>
  </div>
</template>
