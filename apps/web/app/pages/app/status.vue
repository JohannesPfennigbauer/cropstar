<script setup lang="ts">
definePageMeta({ auth: 'public' })

const { t } = useI18n()
const api = useApi()

const { data: status, error, pending, refresh } = await useAsyncData('api-status', async () => {
  const { data, response } = await api.GET('/api/status')
  if (!data) {
    throw createError({ statusCode: response.status, statusMessage: response.statusText })
  }
  return data
})

useSeoMeta({
  title: () => t('app.status.title'),
  robots: 'noindex, nofollow'
})
</script>

<template>
  <div class="min-h-screen bg-default text-default">
    <main class="container-page py-16">
      <h1 class="text-3xl font-semibold text-highlighted">
        {{ t('app.status.title') }}
      </h1>
      <p class="mt-2 text-muted">
        {{ t('app.status.lead') }}
      </p>

      <UCard class="mt-8 max-w-xl">
        <dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3">
          <dt class="text-muted">
            {{ t('app.status.api') }}
          </dt>
          <dd>
            <UBadge
              v-if="pending"
              color="neutral"
              variant="subtle"
              :label="t('app.status.checking')"
            />
            <UBadge
              v-else-if="error || !status"
              color="error"
              variant="subtle"
              :label="t('app.status.unreachable')"
            />
            <UBadge
              v-else
              color="success"
              variant="subtle"
              :label="t('app.status.reachableVersion', { version: status.version })"
            />
          </dd>

          <template v-if="status">
            <dt class="text-muted">
              {{ t('app.status.database') }}
            </dt>
            <dd>
              <UBadge
                :color="status.database.reachable ? 'success' : 'error'"
                variant="subtle"
                :label="status.database.reachable ? t('app.status.reachable') : t('app.status.unreachable')"
              />
            </dd>

            <dt class="text-muted">
              PostgreSQL
            </dt>
            <dd>{{ status.database.postgres_version ?? '–' }}</dd>

            <dt class="text-muted">
              PostGIS
            </dt>
            <dd>{{ status.database.postgis_version ?? t('app.status.notInstalled') }}</dd>
          </template>
        </dl>

        <template #footer>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="outline"
            :loading="pending"
            :label="t('app.status.refresh')"
            @click="refresh()"
          />
        </template>
      </UCard>
    </main>
  </div>
</template>
