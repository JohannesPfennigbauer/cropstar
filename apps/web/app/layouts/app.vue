<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
const { me, farm, signOut } = useAuth()
const { years, selected: harvestYear, load: loadHarvestYears } = useHarvestYear()

await loadHarvestYears()
watch(() => farm.value?.id, () => loadHarvestYears())

const navigation = computed(() => [
  { label: t('app.nav.home'), to: localePath('/app'), exact: true },
  { label: t('app.nav.plots'), to: localePath('/app/plots'), exact: false },
  { label: t('app.nav.tasks'), to: localePath('/app/tasks'), exact: false }
])

function isActive(item: { to: string, exact: boolean }) {
  return item.exact ? route.path === item.to : route.path.startsWith(item.to)
}

// USelect speaks undefined for "nothing selected"; the shared state uses null.
const harvestYearModel = computed({
  get: () => harvestYear.value ?? undefined,
  set: (year: number | undefined) => { harvestYear.value = year ?? null }
})

const yearItems = computed(() => years.value.map(year => ({ label: String(year), value: year })))

useSeoMeta({ robots: 'noindex, nofollow' })

async function onSignOut() {
  await signOut()
  await navigateTo(localePath('/app/sign-in'))
}

const userMenu = computed<DropdownMenuItem[][]>(() => [
  [
    { label: me.value?.user.email ?? '', type: 'label' },
    ...(farm.value ? [{ label: farm.value.name, icon: 'i-lucide-tractor', type: 'label' as const, class: 'sm:hidden' }] : [])
  ],
  navigation.value.map(item => ({ label: item.label, to: item.to, class: 'md:hidden' })),
  [{ label: t('app.nav.account'), icon: 'i-lucide-user-cog', to: localePath('/app/account') }],
  [{ label: t('app.nav.signOut'), icon: 'i-lucide-log-out', onSelect: onSignOut }]
])
</script>

<template>
  <div class="flex min-h-screen flex-col bg-default text-default">
    <header class="sticky top-0 z-50 border-b border-default bg-default/90 backdrop-blur-md">
      <div class="container-page flex h-16 items-center justify-between gap-4">
        <div class="flex min-w-0 items-center gap-4">
          <NuxtLink
            :to="localePath('/app')"
            class="shrink-0"
          >
            <CropstarLogo compact />
          </NuxtLink>
          <span
            v-if="farm"
            class="flex min-w-0 items-center gap-1.5 rounded-full bg-elevated px-3 py-1 text-sm font-medium text-highlighted max-sm:hidden"
            data-testid="current-farm"
          >
            <UIcon
              name="i-lucide-tractor"
              class="size-4 shrink-0 text-primary"
              :aria-label="t('app.nav.farm')"
            />
            <span class="truncate">{{ farm.name }}</span>
          </span>
        </div>

        <nav class="hidden items-center gap-1 md:flex">
          <UButton
            v-for="item in navigation"
            :key="item.to"
            :to="item.to"
            color="neutral"
            :variant="isActive(item) ? 'soft' : 'ghost'"
            size="sm"
            :label="item.label"
          />
        </nav>

        <div class="flex shrink-0 items-center gap-2">
          <USelect
            v-if="years.length"
            v-model="harvestYearModel"
            :items="yearItems"
            icon="i-lucide-wheat"
            size="sm"
            class="w-28"
            :aria-label="t('app.harvestYear.label')"
            :title="t('app.harvestYear.label')"
            data-testid="harvest-year"
          />
          <LocaleSwitch />
          <UDropdownMenu
            :items="userMenu"
            :content="{ align: 'end' }"
          >
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-circle-user-round"
              :aria-label="t('app.nav.userMenu')"
              data-testid="user-menu"
            />
          </UDropdownMenu>
        </div>
      </div>
    </header>

    <main class="container-page flex-1 py-10">
      <slot />
    </main>
  </div>
</template>
