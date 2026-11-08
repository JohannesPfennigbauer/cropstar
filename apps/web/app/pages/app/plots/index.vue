<script setup lang="ts">
// The Plots live on the overview now; old links land there.
const localePath = useLocalePath()
await navigateTo(localePath('/app'), { replace: true })
</script>

<template>
  <div />
</template>
