<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

// Public, not guest: a signed-in user following a reset link must still be able to use it.
definePageMeta({ layout: 'auth', auth: 'public' })

const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
const api = useApi()
const toast = useToast()
const { me } = useAuth()

useSeoMeta({ title: () => t('app.reset.title') })

const token = computed(() => typeof route.query.token === 'string' ? route.query.token : '')

const schema = computed(() => z.object({
  password: z.string().min(8, t('app.validation.passwordLength')).max(256),
  repeat: z.string()
}).refine(data => data.password === data.repeat, {
  message: t('app.validation.passwordsDiffer'),
  path: ['repeat']
}))
type Schema = z.output<typeof schema.value>

const state = reactive({ password: '', repeat: '' })
const errorCode = ref<ApiErrorCode | null>(null)
const submitting = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  errorCode.value = null
  const { response, error } = await api.POST('/api/auth/password-reset/complete', {
    body: { token: token.value, password: event.data.password }
  })
  submitting.value = false
  if (response.status !== 204) {
    errorCode.value = apiErrorCode(error)
    return
  }
  // Every session ended on the server, including this browser's.
  me.value = null
  toast.add({ title: t('app.reset.done'), color: 'success', icon: 'i-lucide-check' })
  await navigateTo(localePath('/app/sign-in'))
}
</script>

<template>
  <UCard>
    <h1 class="text-2xl font-semibold text-highlighted">
      {{ t('app.reset.title') }}
    </h1>

    <UAlert
      v-if="!token"
      class="mt-6"
      color="error"
      variant="subtle"
      icon="i-lucide-link-2-off"
      :description="t('app.reset.missingToken')"
    />

    <template v-else>
      <p class="mt-1 text-muted">
        {{ t('app.reset.lead') }}
      </p>
      <UForm
        :schema="schema"
        :state="state"
        class="mt-6 space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          :label="t('app.fields.newPassword')"
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
        <UFormField
          :label="t('app.fields.repeatPassword')"
          name="repeat"
        >
          <UInput
            v-model="state.repeat"
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
          :label="t('app.reset.submit')"
        />
      </UForm>
    </template>

    <ULink
      :to="localePath('/app/forgot-password')"
      class="mt-6 inline-block text-sm text-primary"
    >
      {{ t('app.reset.requestNew') }}
    </ULink>
  </UCard>
</template>
