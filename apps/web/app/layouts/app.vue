<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

const { t } = useI18n()
const localePath = useLocalePath()
const { me, farm, signOut } = useAuth()

useSeoMeta({ robots: 'noindex, nofollow' })

async function onSignOut() {
  await signOut()
  await navigateTo(localePath('/app/sign-in'))
}

const userMenu = computed<DropdownMenuItem[][]>(() => [
  [{ label: me.value?.user.email ?? '', type: 'label' }],
  [{ label: t('app.nav.account'), icon: 'i-lucide-user-cog', to: localePath('/app/account') }],
  [{ label: t('app.nav.signOut'), icon: 'i-lucide-log-out', onSelect: onSignOut }]
])
</script>

<template>
  <div class="flex min-h-screen flex-col bg-default text-default">
    <header class="sticky top-0 z-50 border-b border-default bg-default/90 backdrop-blur-md">
      <div class="container-page flex h-16 items-center justify-between gap-4">
        <div class="flex min-w-0 items-center gap-4">
          <NuxtLink :to="localePath('/app')">
            <CropstarLogo />
          </NuxtLink>
          <span
            v-if="farm"
            class="flex min-w-0 items-center gap-1.5 rounded-full bg-elevated px-3 py-1 text-sm font-medium text-highlighted"
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

        <div class="flex items-center gap-2">
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
