<script setup lang="ts">
const { t } = useI18n()
const { repositoryUrl } = useRuntimeConfig().public
const year = new Date().getFullYear()
</script>

<template>
  <footer class="border-t border-default py-10">
    <div class="container-page flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-sm text-muted">
        {{ t('footer.rights', { year }) }}
      </p>
      <div class="flex items-center gap-4 text-sm">
        <ULink
          :to="repositoryUrl"
          target="_blank"
          rel="noopener"
          class="text-muted hover:text-highlighted"
        >
          {{ t('footer.source') }}
        </ULink>
        <ULink
          :to="`${repositoryUrl}/issues`"
          target="_blank"
          rel="noopener"
          class="text-muted hover:text-highlighted"
        >
          {{ t('footer.issues') }}
        </ULink>
      </div>
    </div>
  </footer>
</template>
