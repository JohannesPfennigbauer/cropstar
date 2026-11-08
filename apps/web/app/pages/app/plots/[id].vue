<script setup lang="ts">
// A Plot opens in place on the overview now; old links land there, opened.
const route = useRoute()
const localePath = useLocalePath()
await navigateTo(localePath({ path: '/app', query: { plot: String(route.params.id) } }), { replace: true })
</script>

<template>
  <div />
</template>
