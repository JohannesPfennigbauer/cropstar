<script setup lang="ts">
import type { Activity } from '~/utils/activities'

/**
 * A Plot's Activities as a table: undated Tasks by priority on top, then newest first with a "today" line.
 * The row background is the ground cover derived from the Operations; the reason is in the row's tooltip.
 */
const props = defineProps<{ activities: Activity[] }>()
const emit = defineEmits<{ select: [activity: Activity] }>()

const { t } = useI18n()
const { day } = useFormat()
const today = todayIso()
const { look } = useActivityCover(() => props.activities)

const rows = computed(() => newestFirst(props.activities))
// "Today" sits above the first Activity that is not in the future.
const todayKey = computed(() => rows.value.find(a => a.date && a.date <= today)?.key ?? null)
</script>

<template>
  <div class="mt-2 max-h-64 overflow-y-auto rounded-md border border-default">
    <table
      class="w-full text-left text-xs"
      data-testid="plot-history"
    >
      <tbody class="divide-y divide-default">
        <template
          v-for="activity in rows"
          :key="activity.key"
        >
          <tr
            v-if="activity.key === todayKey"
            class="bg-inverted text-inverted"
            data-testid="activities-today"
          >
            <td
              colspan="4"
              class="py-0.5 pl-2 font-display font-semibold"
            >
              {{ t('app.activities.today') }}
            </td>
          </tr>
          <tr
            :class="activity.task ? 'cursor-pointer hover:brightness-95' : ''"
            :style="{ background: activity.date ? look(activity, 30).background : undefined }"
            :title="look(activity).why"
            :data-testid="activity.done ? 'plot-log-row' : 'plot-task-row'"
            @click="emit('select', activity)"
          >
            <td class="w-6 py-1.5 pl-2 align-top">
              <UIcon
                :name="operationIcon(activity.operationType)"
                class="mt-0.5 size-3.5"
                :class="activity.done ? 'text-primary' : 'text-muted'"
                :aria-label="activity.done ? t('app.tasks.status.done') : t('app.tasks.status.open')"
              />
            </td>
            <td
              class="w-24 py-1.5 align-top whitespace-nowrap tabular-nums"
              :class="activity.task && isOverdue(activity.task, today) ? 'font-semibold text-error' : 'text-toned'"
            >
              {{ activity.date ? day(activity.date) : '–' }}
            </td>
            <td class="py-1.5 pr-2 align-top">
              <span
                class="block font-medium text-highlighted"
                :class="activity.done ? '' : 'italic'"
              >{{ activity.title }}</span>
              <span
                v-if="activity.detail"
                class="block text-toned"
              >{{ activity.detail }}</span>
              <AppNutrientsApplied
                v-if="activity.applied"
                :applied="activity.applied"
              />
            </td>
            <td class="w-6 py-1.5 pr-2 text-center align-top">
              <UIcon
                v-if="!activity.done && priorityIcon(activity.priority)"
                :name="priorityIcon(activity.priority)!"
                class="mt-0.5 size-3.5"
                :aria-label="t('app.activities.priority', { level: t(`app.tasks.priority.${activity.priority}`) })"
              />
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>
