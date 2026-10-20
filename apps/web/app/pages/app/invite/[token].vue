<script setup lang="ts">
// Public: the link must make sense before anyone has an account.
definePageMeta({ layout: 'auth', auth: 'public' })

const { t } = useI18n()
const api = useApi()
const route = useRoute()
const localePath = useLocalePath()
const toast = useToast()
const { me, ensure, refresh, selectFarm } = useAuth()
const { moment } = useFormat()

useSeoMeta({ title: () => t('app.invite.title') })

const token = computed(() => String(route.params.token))
await ensure()

const { data: preview } = await useAsyncData(`invitation-${token.value}`, async () =>
  (await api.GET('/api/invitations/{token}', { params: { path: { token: token.value } } })).data ?? null)

const busy = ref(false)
const errorCode = ref<string | null>(null)

async function accept() {
  busy.value = true
  const before = new Set(me.value?.memberships.map(m => m.farm.id))
  const { data, error } = await api.POST('/api/invitations/{token}/accept', {
    params: { path: { token: token.value } }
  })
  busy.value = false
  if (!data) {
    errorCode.value = String((error as { detail?: unknown } | undefined)?.detail ?? 'unknown')
    return
  }
  await refresh()
  const joined = data.memberships.find(m => !before.has(m.farm.id))
  if (joined) selectFarm(joined.farm.id)
  toast.add({ title: t('app.invite.joined', { farm: preview.value?.farm_name ?? '' }), color: 'success', icon: 'i-lucide-check' })
  await navigateTo(localePath('/app'))
}
</script>

<template>
  <UCard>
    <h1 class="text-2xl font-semibold text-highlighted">
      {{ t('app.invite.title') }}
    </h1>

    <UAlert
      v-if="!preview"
      class="mt-6"
      color="error"
      variant="subtle"
      icon="i-lucide-link-2-off"
      :description="t('app.invite.notFound')"
    />

    <template v-else>
      <p class="mt-3 text-toned">
        {{ t('app.invite.lead', { farm: preview.farm_name, role: t(`app.roles.${preview.role}`) }) }}
      </p>
      <p
        v-if="preview.invited_by"
        class="mt-1 text-sm text-muted"
      >
        {{ t('app.invite.by', { email: preview.invited_by }) }}
      </p>

      <UAlert
        v-if="preview.state !== 'valid'"
        class="mt-6"
        color="warning"
        variant="subtle"
        icon="i-lucide-clock-alert"
        :description="t(`app.invite.state.${preview.state}`)"
      />

      <template v-else>
        <p class="mt-1 text-xs text-dimmed">
          {{ t('app.invite.validUntil', { date: moment(preview.expires_at) }) }}
        </p>

        <div
          v-if="me"
          class="mt-6 space-y-3"
        >
          <p class="text-sm text-muted">
            {{ t('app.invite.signedInAs', { email: me.user.email }) }}
          </p>
          <UAlert
            v-if="errorCode"
            color="error"
            variant="subtle"
            :description="t(`app.invite.errors.${errorCode}`, t('app.errors.unknown'))"
          />
          <UButton
            block
            :loading="busy"
            :label="t('app.invite.join', { farm: preview.farm_name })"
            data-testid="accept-invitation"
            @click="accept"
          />
        </div>

        <div
          v-else
          class="mt-6 flex flex-col gap-2"
        >
          <UButton
            block
            :to="{ path: localePath('/app/register'), query: { invitation: token } }"
            :label="t('app.invite.register')"
          />
          <UButton
            block
            color="neutral"
            variant="outline"
            :to="{ path: localePath('/app/sign-in'), query: { redirect: route.fullPath } }"
            :label="t('app.invite.signIn')"
          />
        </div>
      </template>
    </template>
  </UCard>
</template>
