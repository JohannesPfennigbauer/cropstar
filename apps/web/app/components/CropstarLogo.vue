<script setup lang="ts">
// Compact hides the wordmark on narrow screens, where the header needs the room.
defineProps<{ compact?: boolean }>()
</script>

<template>
  <span class="flex items-center gap-2.5">
    <svg
      viewBox="0 0 24 24"
      class="size-7 text-primary"
      aria-hidden="true"
    >
      <path
        d="M12 22V9"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        fill="none"
      />
      <path
        d="M12 9c0-2.5 1.4-4.6 3.4-5.6C15.4 6 14 8.2 12 9Zm0 0C12 6.5 10.6 4.4 8.6 3.4 8.6 6 10 8.2 12 9Zm0 4.6c0-2.3 1.3-4.2 3.1-5.1.1 2.4-1.2 4.4-3.1 5.1Zm0 0c0-2.3-1.3-4.2-3.1-5.1-.1 2.4 1.2 4.4 3.1 5.1Zm0 4.6c0-2.3 1.3-4.2 3.1-5.1.1 2.4-1.2 4.4-3.1 5.1Zm0 0c0-2.3-1.3-4.2-3.1-5.1-.1 2.4 1.2 4.4 3.1 5.1Z"
        fill="currentColor"
      />
    </svg>
    <span
      class="font-display text-xl font-semibold text-highlighted"
      :class="{ 'max-sm:sr-only': compact }"
    >Cropstar</span>
  </span>
</template>
