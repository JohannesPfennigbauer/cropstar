<script setup lang="ts">
const { t } = useI18n()
const localePath = useLocalePath()
</script>

<template>
  <div class="flex items-center gap-4 text-sm">
    <ULink
      :to="localePath('imprint')"
      class="text-muted hover:text-highlighted"
    >
      {{ t('legal.imprint') }}
    </ULink>
    <ULink
      :to="localePath('privacy')"
      class="text-muted hover:text-highlighted"
    >
      {{ t('legal.privacy') }}
    </ULink>
  </div>
</template>
