<script setup lang="ts">
import type { BlogLocale } from '#shared/blog'

const props = defineProps<{
  post: PostSummary
  to: string
}>()

const { t, locale } = useI18n()
const { formatDate } = useFigures()

const foreign = computed(() => props.post.lang !== (locale.value as BlogLocale))
</script>

<template>
  <NuxtLink
    :to="to"
    class="group flex h-full flex-col overflow-hidden rounded-2xl border border-default bg-default transition-colors hover:border-accented hover:bg-elevated/50"
  >
    <img
      v-if="post.cover"
      :src="post.cover.src"
      :alt="post.cover.alt"
      class="aspect-[16/9] w-full object-cover"
      loading="lazy"
    >
    <div class="flex flex-1 flex-col p-5">
      <div class="flex flex-wrap items-center gap-2">
        <UBadge
          :label="t(`blog.topics.${post.topic}`)"
          color="primary"
          variant="soft"
          size="sm"
        />
        <UBadge
          v-if="foreign"
          :label="t(`blog.languages.${post.lang}`)"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-languages"
        />
        <UBadge
          v-if="post.draft"
          :label="t('blog.draft')"
          color="warning"
          variant="soft"
          size="sm"
        />
      </div>
      <h2
        class="mt-4 text-2xl font-semibold leading-snug text-highlighted group-hover:text-primary"
        :lang="foreign ? post.lang : undefined"
      >
        {{ post.title }}
      </h2>
      <p
        class="mt-2 flex-1 text-muted"
        :lang="foreign ? post.lang : undefined"
      >
        {{ post.description }}
      </p>
      <p class="mt-4 text-sm text-dimmed">
        <time :datetime="new Date(post.date).toISOString().slice(0, 10)">{{ formatDate(post.date) }}</time>
      </p>
    </div>
  </NuxtLink>
</template>
