<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'auth', auth: 'guest' })

const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
const api = useApi()
const { signIn } = useAuth()

useSeoMeta({ title: () => t('app.signIn.title') })

const { data: config } = await useAsyncData('auth-config', async () => (await api.GET('/api/auth/config')).data)

const schema = computed(() => z.object({
  email: z.string().trim().min(1, t('app.validation.required')),
  password: z.string().min(1, t('app.validation.required'))
}))
type Schema = z.output<typeof schema.value>

const state = reactive({ email: '', password: '' })
const errorCode = ref<ApiErrorCode | null>(null)
const submitting = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  errorCode.value = null
  const result = await signIn(event.data.email, event.data.password)
  submitting.value = false
  if (!result.ok) {
    errorCode.value = result.code
    return
  }
  await navigateTo(safeRedirect(route.query.redirect, localePath('/app')))
}
</script>

<template>
  <UCard>
    <h1 class="text-2xl font-semibold text-highlighted">
      {{ t('app.signIn.title') }}
    </h1>
    <p class="mt-1 text-muted">
      {{ t('app.signIn.lead') }}
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
      <UFormField
        :label="t('app.fields.password')"
        name="password"
      >
        <UInput
          v-model="state.password"
          type="password"
          autocomplete="current-password"
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
        :label="t('app.signIn.submit')"
      />
    </UForm>

    <div class="mt-6 flex flex-col gap-2 text-sm">
      <ULink
        :to="localePath('/app/forgot-password')"
        class="text-primary"
      >
        {{ t('app.signIn.forgot') }}
      </ULink>
      <p
        v-if="config?.registration_open"
        class="text-muted"
      >
        {{ t('app.signIn.noAccount') }}
        <ULink
          :to="localePath('/app/register')"
          class="text-primary"
        >
          {{ t('app.signIn.register') }}
        </ULink>
      </p>
    </div>
  </UCard>
</template>
