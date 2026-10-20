<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'app' })

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { me } = useAuth()

useSeoMeta({ title: () => t('app.account.title') })

const schema = computed(() => z.object({
  current_password: z.string().min(1, t('app.validation.required')),
  new_password: z.string().min(8, t('app.validation.passwordLength')).max(256)
}))
type Schema = z.output<typeof schema.value>

const form = useTemplateRef('form')
const state = reactive({ current_password: '', new_password: '' })
const errorCode = ref<ApiErrorCode | null>(null)
const submitting = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  errorCode.value = null
  const { response, error } = await api.POST('/api/auth/password', { body: event.data })
  submitting.value = false
  if (response.status !== 204) {
    errorCode.value = apiErrorCode(error)
    return
  }
  state.current_password = ''
  state.new_password = ''
  form.value?.clear()
  toast.add({ title: t('app.account.changed'), color: 'success', icon: 'i-lucide-check' })
}
</script>

<template>
  <div class="max-w-xl">
    <h1 class="text-3xl font-semibold text-highlighted">
      {{ t('app.account.title') }}
    </h1>
    <p class="mt-2 text-muted">
      {{ t('app.account.signedInAs', { email: me?.user.email ?? '' }) }}
    </p>

    <UCard class="mt-8">
      <h2 class="text-lg font-semibold text-highlighted">
        {{ t('app.account.changePassword') }}
      </h2>
      <p class="mt-1 text-sm text-muted">
        {{ t('app.account.changePasswordLead') }}
      </p>
      <UForm
        ref="form"
        :schema="schema"
        :state="state"
        class="mt-6 space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          :label="t('app.fields.currentPassword')"
          name="current_password"
        >
          <UInput
            v-model="state.current_password"
            type="password"
            autocomplete="current-password"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('app.fields.newPassword')"
          :help="t('app.hints.password')"
          name="new_password"
        >
          <UInput
            v-model="state.new_password"
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
          :loading="submitting"
          :label="t('app.account.submit')"
        />
      </UForm>
    </UCard>
  </div>
</template>
