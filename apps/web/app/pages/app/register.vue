<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'auth', auth: 'guest' })

const { t } = useI18n()
const localePath = useLocalePath()
const api = useApi()
const { register } = useAuth()

useSeoMeta({ title: () => t('app.register.title') })

const { data: config } = await useAsyncData('auth-config', async () => (await api.GET('/api/auth/config')).data)

const schema = computed(() => z.object({
  farm_name: z.string().trim().min(1, t('app.validation.required')).max(200),
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
  const result = await register(event.data)
  submitting.value = false
  if (!result.ok) {
    errorCode.value = result.code
    return
  }
  await navigateTo(localePath('/app'))
}
</script>

<template>
  <UCard>
    <h1 class="text-2xl font-semibold text-highlighted">
      {{ t('app.register.title') }}
    </h1>

    <UAlert
      v-if="config && !config.registration_open"
      class="mt-6"
      color="neutral"
      variant="subtle"
      icon="i-lucide-lock"
      :title="t('app.register.closedTitle')"
      :description="t('app.register.closed')"
    />

    <template v-else>
      <p class="mt-1 text-muted">
        {{ t('app.register.lead') }}
      </p>

      <UForm
        :schema="schema"
        :state="state"
        class="mt-6 space-y-4"
        @submit="onSubmit"
      >
        <UFormField
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
          :label="t('app.register.submit')"
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
