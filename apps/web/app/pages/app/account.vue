<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'app' })

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { me } = useAuth()
const localePath = useLocalePath()

const deletion = reactive({ password: '' })
const deleting = ref(false)
const deletionError = ref<string | null>(null)

async function deleteAccount() {
  deleting.value = true
  deletionError.value = null
  const { response, error } = await api.DELETE('/api/me', { body: { password: deletion.password } })
  deleting.value = false
  if (response.status === 204) {
    me.value = null
    toast.add({ title: t('app.account.deleted'), color: 'neutral', icon: 'i-lucide-trash-2' })
    await navigateTo(localePath('/'))
    return
  }
  const detail = (error as { detail?: unknown } | undefined)?.detail
  deletionError.value = typeof detail === 'object' && detail && 'farms' in detail
    ? t('app.account.handOver', { farms: (detail as { farms: string[] }).farms.join(', ') })
    : t(`app.errors.${apiErrorCode(error)}`)
}

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

    <UCard class="mt-8 ring-error/40">
      <h2 class="text-lg font-semibold text-error">
        {{ t('app.account.deleteTitle') }}
      </h2>
      <p class="mt-1 text-sm text-muted">
        {{ t('app.account.deleteLead') }}
      </p>
      <div class="mt-4 flex flex-col gap-2 sm:flex-row">
        <UInput
          v-model="deletion.password"
          type="password"
          autocomplete="current-password"
          :placeholder="t('app.fields.currentPassword')"
          :aria-label="t('app.fields.currentPassword')"
          class="w-full sm:w-72"
        />
        <UButton
          color="error"
          icon="i-lucide-trash-2"
          :disabled="!deletion.password"
          :loading="deleting"
          :label="t('app.account.delete')"
          @click="deleteAccount"
        />
      </div>
      <UAlert
        v-if="deletionError"
        class="mt-4"
        color="error"
        variant="subtle"
        :description="deletionError"
      />
    </UCard>
  </div>
</template>
