<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const open = defineModel<boolean>('open', { required: true })

const { t } = useI18n()
const localePath = useLocalePath()
const toast = useToast()
const { createFarm } = useAuth()

const schema = computed(() => z.object({
  name: z.string().trim().min(1, t('app.validation.required')).max(200)
}))
type Schema = z.output<typeof schema.value>

const state = reactive({ name: '' })
const busy = ref(false)
const errorCode = ref<ApiErrorCode | null>(null)

watch(open, (isOpen) => {
  if (isOpen) {
    state.name = ''
    errorCode.value = null
  }
})

async function onSubmit(event: FormSubmitEvent<Schema>) {
  busy.value = true
  const result = await createFarm(event.data.name)
  busy.value = false
  if (!result.ok) {
    errorCode.value = result.code
    return
  }
  open.value = false
  toast.add({ title: t('app.farm.created', { name: event.data.name }), color: 'success', icon: 'i-lucide-check' })
  await navigateTo(localePath('/app'))
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('app.farm.createTitle')"
    :description="t('app.farm.createLead')"
  >
    <template #body>
      <UForm
        id="create-farm-form"
        :schema="schema"
        :state="state"
        @submit="onSubmit"
      >
        <UFormField
          :label="t('app.fields.farmName')"
          name="name"
        >
          <UInput
            v-model="state.name"
            class="w-full"
            autofocus
          />
        </UFormField>
        <UAlert
          v-if="errorCode"
          class="mt-4"
          color="error"
          variant="subtle"
          :description="t(`app.errors.${errorCode}`)"
        />
      </UForm>
    </template>
    <template #footer>
      <UButton
        type="submit"
        form="create-farm-form"
        class="ml-auto"
        :loading="busy"
        :label="t('app.farm.create')"
      />
    </template>
  </UModal>
</template>
