<script setup lang="ts">
/** One Activity as an upright card on the spiral, hanging from a pin like a note on a line. */
const props = defineProps<{ activity: Activity, background: string, why: string }>()
defineEmits<{ select: [] }>()

const { t } = useI18n()
const { shortDay } = useFormat()

const icon = computed(() => operationIcon(props.activity.operationType))
const priority = computed(() => (props.activity.done ? null : priorityIcon(props.activity.priority)))
</script>

<template>
  <button
    type="button"
    class="activity-card relative flex w-40 flex-col gap-0.5 rounded-md px-2.5 pt-3 pb-2 text-left text-xs text-highlighted"
    :class="{ open: !activity.done, clickable: !!activity.task }"
    :style="{ background }"
    :title="why"
    data-testid="activity-card"
    @click="$emit('select')"
  >
    <span
      class="pin absolute left-1/2 h-4 -translate-x-1/2 rounded-sm"
      aria-hidden="true"
    />
    <span class="dim flex items-center gap-1.5">
      <UIcon
        :name="icon"
        class="size-3.5 shrink-0"
      />
      <span class="tabular-nums">{{ activity.date ? shortDay(activity.date) : t('app.activities.undated') }}</span>
      <UIcon
        v-if="activity.done"
        name="i-lucide-circle-check"
        class="ml-auto size-3.5"
        :aria-label="t('app.tasks.status.done')"
      />
      <UIcon
        v-else-if="priority"
        :name="priority"
        class="ml-auto size-3.5"
        :aria-label="t('app.activities.priority', { level: t(`app.tasks.priority.${activity.priority}`) })"
      />
    </span>
    <span class="font-display text-sm leading-tight font-medium">{{ activity.title }}</span>
    <span
      v-if="activity.detail"
      class="dim leading-tight"
    >{{ activity.detail }}</span>
  </button>
</template>

<style scoped>
.activity-card {
  cursor: default;
  box-shadow: 0 4px 10px rgb(0 0 0 / 0.15), 0 0 0 1px rgb(0 0 0 / 0.08);
  transition: box-shadow 150ms;
}
.activity-card.clickable {
  cursor: pointer;
}
.activity-card.clickable:hover {
  box-shadow: 0 8px 18px rgb(0 0 0 / 0.22), 0 0 0 1px rgb(0 0 0 / 0.08);
}
.activity-card.open {
  outline: 2px dashed rgb(52 55 47 / 0.45);
  outline-offset: -2px;
}
.pin {
  top: -0.5rem;
  width: 0.375rem;
  background: var(--color-soil-700);
}
.dim {
  opacity: 0.8;
}
</style>
