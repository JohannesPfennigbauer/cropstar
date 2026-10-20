<script setup lang="ts">
/** Explains why everything referring to a Locked Harvest Year is read-only. Renders nothing when open. */
const props = defineProps<{ year: number | null | undefined }>()

const { t } = useI18n()
const { moment } = useFormat()
const { membership } = useAuth()
const { lockOf } = useHarvestYear()

const lock = computed(() => lockOf(props.year))
const description = computed(() => {
  if (!lock.value) return ''
  return [
    t('app.harvestYear.lockedBy', {
      person: lock.value.locked_by?.email ?? t('app.tasks.formerMember'),
      date: moment(lock.value.locked_at)
    }),
    t('app.harvestYear.lockedHint'),
    membership.value?.role === 'admin' ? t('app.harvestYear.unlockHintAdmin') : t('app.harvestYear.unlockHint')
  ].join(' ')
})
</script>

<template>
  <UAlert
    v-if="lock"
    color="neutral"
    variant="subtle"
    icon="i-lucide-lock"
    :title="t('app.harvestYear.locked', { year })"
    :description="description"
    data-testid="lock-notice"
  />
</template>
