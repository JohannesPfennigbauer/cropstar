<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'auth', auth: 'guest' })

const { t, locale } = useI18n()
const localePath = useLocalePath()
const api = useApi()

useSeoMeta({ title: () => t('app.forgot.title') })

const { data: config } = await useAsyncData('auth-config', async () => (await api.GET('/api/auth/config')).data)

const schema = computed(() => z.object({
  email: z.string().trim().email(t('app.validation.email'))
}))
type Schema = z.output<typeof schema.value>

const state = reactive({ email: '' })
const sentTo = ref<string | null>(null)
const errorCode = ref<ApiErrorCode | null>(null)
const submitting = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  errorCode.value = null
  const { response, error } = await api.POST('/api/auth/password-reset/request', {
    body: { email: event.data.email, locale: locale.value === 'en' ? 'en' : 'de' }
  })
  submitting.value = false
  if (response.status === 202) sentTo.value = event.data.email
  else errorCode.value = apiErrorCode(error)
}
</script>

<template>
  <UCard>
    <h1 class="text-2xl font-semibold text-highlighted">
      {{ t('app.forgot.title') }}
    </h1>

    <UAlert
      v-if="config && !config.password_reset_by_email"
      class="mt-6"
      color="neutral"
      variant="subtle"
      icon="i-lucide-life-buoy"
      :title="t('app.forgot.noEmailTitle')"
      :description="t('app.forgot.noEmail')"
    />

    <UAlert
      v-else-if="sentTo"
      class="mt-6"
      color="success"
      variant="subtle"
      icon="i-lucide-mail-check"
      :title="t('app.forgot.sentTitle')"
      :description="t('app.forgot.sent', { email: sentTo })"
    />

    <template v-else>
      <p class="mt-1 text-muted">
        {{ t('app.forgot.lead') }}
      </p>
      <UForm
        :schema="schema"
        :state="state"
        class="mt-6 space-y-4"
        @submit="onSubmit"
      >
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
          :label="t('app.forgot.submit')"
        />
      </UForm>
    </template>

    <ULink
      :to="localePath('/app/sign-in')"
      class="mt-6 inline-block text-sm text-primary"
    >
      {{ t('app.forgot.back') }}
    </ULink>
  </UCard>
</template>
