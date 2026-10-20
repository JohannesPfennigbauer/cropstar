<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'auth', auth: 'guest' })

const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
const api = useApi()
const { register, selectFarm, me } = useAuth()

// Arriving from an invitation link: join that Farm instead of creating one.
const invitationToken = computed(() =>
  typeof route.query.invitation === 'string' ? route.query.invitation : null)
const { data: invitation } = await useAsyncData('register-invitation', async () => {
  if (!invitationToken.value) return null
  const { data } = await api.GET('/api/invitations/{token}', {
    params: { path: { token: invitationToken.value } }
  })
  return data?.state === 'valid' ? data : null
})

useSeoMeta({ title: () => t(invitation.value ? 'app.register.joinTitle' : 'app.register.title') })

const { data: config } = await useAsyncData('auth-config', async () => (await api.GET('/api/auth/config')).data)

const schema = computed(() => z.object({
  farm_name: invitation.value
    ? z.string()
    : z.string().trim().min(1, t('app.validation.required')).max(200),
  email: z.string().trim().email(t('app.validation.email')),
  password: z.string().min(8, t('app.validation.passwordLength')).max(256)
}))
type Schema = z.output<typeof schema.value>

const state = reactive({ farm_name: '', email: '', password: '' })
const errorCode = ref<ApiErrorCode | null>(null)
const submitting = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  errorCode.value = null
  const result = await register(invitation.value
    ? { email: event.data.email, password: event.data.password, invitation_token: invitationToken.value }
    : event.data)
  submitting.value = false
  if (!result.ok) {
    errorCode.value = result.code
    return
  }
  const joined = me.value?.memberships[0]
  if (joined) selectFarm(joined.farm.id)
  await navigateTo(localePath('/app'))
}
</script>

<template>
  <UCard>
    <h1 class="text-2xl font-semibold text-highlighted">
      {{ t(invitation ? 'app.register.joinTitle' : 'app.register.title') }}
    </h1>

    <UAlert
      v-if="invitation"
      class="mt-6"
      color="primary"
      variant="subtle"
      icon="i-lucide-handshake"
      :description="t('app.invite.lead', { farm: invitation.farm_name, role: t(`app.roles.${invitation.role}`) })"
    />

    <UAlert
      v-if="config && !config.registration_open && !invitation"
      class="mt-6"
      color="neutral"
      variant="subtle"
      icon="i-lucide-lock"
      :title="t('app.register.closedTitle')"
      :description="t('app.register.closed')"
    />

    <template v-else>
      <p
        v-if="!invitation"
        class="mt-1 text-muted"
      >
        {{ t('app.register.lead') }}
      </p>

      <UForm
        :schema="schema"
        :state="state"
        class="mt-6 space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          v-if="!invitation"
          :label="t('app.fields.farmName')"
          :help="t('app.hints.farmName')"
          name="farm_name"
        >
          <UInput
            v-model="state.farm_name"
            autocomplete="organization"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('app.fields.email')"
          name="email"
        >
          <UInput
            v-model="state.email"
            type="email"
            autocomplete="username"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('app.fields.password')"
          :help="t('app.hints.password')"
          name="password"
        >
          <UInput
            v-model="state.password"
            type="password"
            autocomplete="new-password"
            class="w-full"
          />
        </UFormField>

        <UAlert
          v-if="errorCode"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :description="t(`app.errors.${errorCode}`)"
        />

        <UButton
          type="submit"
          block
          :loading="submitting"
          :label="t(invitation ? 'app.register.joinSubmit' : 'app.register.submit')"
        />
      </UForm>
    </template>

    <p class="mt-6 text-sm text-muted">
      {{ t('app.register.haveAccount') }}
      <ULink
        :to="localePath('/app/sign-in')"
        class="text-primary"
      >
        {{ t('app.register.signIn') }}
      </ULink>
    </p>
  </UCard>
</template>
