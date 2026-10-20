<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

const { t } = useI18n()
const localePath = useLocalePath()
const { me, farm, selectFarm } = useAuth()
const creating = ref(false)

const items = computed<DropdownMenuItem[][]>(() => [
  (me.value?.memberships ?? []).map(m => ({
    label: m.farm.name,
    icon: m.farm.id === farm.value?.id ? 'i-lucide-check' : 'i-lucide-tractor',
    description: t(`app.roles.${m.role}`),
    onSelect: () => selectFarm(m.farm.id)
  })),
  [
    { label: t('app.farm.manage'), icon: 'i-lucide-settings', to: localePath('/app/farm') },
    { label: t('app.farm.createTitle'), icon: 'i-lucide-plus', onSelect: () => { creating.value = true } }
  ]
])
</script>

<template>
  <UDropdownMenu
    :items="items"
    :content="{ align: 'start' }"
  >
    <button
      type="button"
      class="flex min-w-0 items-center gap-1.5 rounded-full bg-elevated px-3 py-1 text-sm font-medium text-highlighted transition-colors hover:bg-accented max-sm:hidden"
      :aria-label="t('app.farm.switch')"
      data-testid="farm-switcher"
    >
      <UIcon
        name="i-lucide-tractor"
        class="size-4 shrink-0 text-primary"
      />
      <span
        class="truncate"
        data-testid="current-farm"
      >{{ farm?.name ?? t('app.farm.none') }}</span>
      <UIcon
        name="i-lucide-chevrons-up-down"
        class="size-3.5 shrink-0 text-muted"
      />
    </button>
  </UDropdownMenu>
  <AppCreateFarmDialog v-model:open="creating" />
</template>
