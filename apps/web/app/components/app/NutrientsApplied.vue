<script setup lang="ts">
import type { Schemas } from '@cropstar/api-client'

/** What a fertilisation applied per hectare, and where the contents behind it come from. */
const props = defineProps<{ applied: Schemas['AppliedInput'] | null | undefined }>()

const { nutrients, nutrientSource } = useOperationDetails()
const line = computed(() => nutrients(props.applied))
const source = computed(() => nutrientSource(props.applied))
</script>

<template>
  <span
    v-if="line"
    class="block text-xs"
    data-testid="nutrients-applied"
  >
    <span class="text-toned tabular-nums">{{ line }}</span>
    <span
      v-if="source"
      class="flex items-start gap-1 text-muted"
    >
      <UIcon
        name="i-lucide-book-open"
        class="mt-0.5 size-3 shrink-0"
      />
      {{ source }}
    </span>
  </span>
</template>
