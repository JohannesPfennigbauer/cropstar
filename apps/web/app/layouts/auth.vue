<script setup lang="ts">
const localePath = useLocalePath()

useSeoMeta({ robots: 'noindex, nofollow' })
</script>

<template>
  <div class="flex min-h-screen flex-col bg-default text-default">
    <header class="container-page flex h-18 items-center justify-between gap-4">
      <NuxtLink :to="localePath('/')">
        <CropstarLogo />
      </NuxtLink>
      <LocaleSwitch />
    </header>

    <main class="container-page flex flex-1 items-start justify-center py-10 sm:items-center">
      <div class="w-full max-w-md">
        <slot />
      </div>
    </main>
  </div>
</template>
