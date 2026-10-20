<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Schemas } from '@cropstar/api-client'

definePageMeta({ layout: 'app' })

type Role = Schemas['Role']
const ROLES: Role[] = ['admin', 'worker', 'advisor']

const { t, locale } = useI18n()
const api = useApi()
const toast = useToast()
const localePath = useLocalePath()
const { me, farm, refresh: refreshMe } = useAuth()
const { day, moment } = useFormat()

useSeoMeta({ title: () => t('app.farm.title') })

const path = computed(() => ({ farm_id: farm.value?.id ?? '' }))

const { data: details, refresh: refreshDetails } = await useAsyncData('farm', async () => {
  if (!farm.value) return null
  return (await api.GET('/api/farms/{farm_id}', { params: { path: path.value } })).data ?? null
}, { watch: [() => farm.value?.id] })

const isAdmin = computed(() => details.value?.role === 'admin')

const { data: members, refresh: refreshMembers } = await useAsyncData('farm-members', async () => {
  if (!farm.value) return []
  return (await api.GET('/api/farms/{farm_id}/members', { params: { path: path.value } })).data ?? []
}, { watch: [() => farm.value?.id] })

const { data: invitations, refresh: refreshInvitations } = await useAsyncData('farm-invitations', async () => {
  if (!farm.value || !isAdmin.value) return []
  return (await api.GET('/api/farms/{farm_id}/invitations', { params: { path: path.value } })).data ?? []
}, { watch: [() => farm.value?.id, isAdmin] })

const { data: config } = await useAsyncData('auth-config', async () => (await api.GET('/api/auth/config')).data)

function failed(error: unknown) {
  const code = apiErrorCode(error) === 'unknown'
    ? String((error as { detail?: unknown } | undefined)?.detail ?? 'unknown')
    : apiErrorCode(error)
  toast.add({ title: t(`app.farm.errors.${code}`, t('app.errors.unknown')), color: 'error', icon: 'i-lucide-circle-alert' })
}

// ── Master data ──────────────────────────────────────────────────────────
const masterSchema = z.object({
  name: z.string().trim().min(1).max(200),
  ama_farm_number: z.string().trim().regex(/^[0-9]*$/, t('app.farm.amaNumberDigits')).max(20)
})
const master = reactive({ name: '', ama_farm_number: '' })
watch(details, (value) => {
  master.name = value?.name ?? ''
  master.ama_farm_number = value?.ama_farm_number ?? ''
}, { immediate: true })
const savingMaster = ref(false)

async function saveMaster(event: FormSubmitEvent<z.output<typeof masterSchema>>) {
  savingMaster.value = true
  const { data, error } = await api.PATCH('/api/farms/{farm_id}', {
    params: { path: path.value },
    body: { name: event.data.name, ama_farm_number: event.data.ama_farm_number || null }
  })
  savingMaster.value = false
  if (!data) return failed(error)
  details.value = data
  await refreshMe()
  toast.add({ title: t('app.tasks.saved'), color: 'success', icon: 'i-lucide-check' })
}

// ── Members ──────────────────────────────────────────────────────────────
const roleItems = computed(() => ROLES.map(role => ({ label: t(`app.roles.${role}`), value: role })))

async function changeRole(userId: string, role: Role) {
  const { data, error } = await api.PATCH('/api/farms/{farm_id}/members/{user_id}', {
    params: { path: { ...path.value, user_id: userId } },
    body: { role }
  })
  if (!data) failed(error)
  await Promise.all([refreshMembers(), refreshDetails(), refreshMe()])
}

const removing = ref<Schemas['MemberOut'] | null>(null)

async function removeMember() {
  if (!removing.value) return
  const leaving = removing.value.user.id === me.value?.user.id
  const { response, error } = await api.DELETE('/api/farms/{farm_id}/members/{user_id}', {
    params: { path: { ...path.value, user_id: removing.value.user.id } }
  })
  removing.value = null
  if (response.status !== 204) return failed(error)
  if (leaving) {
    await refreshMe()
    toast.add({ title: t('app.farm.left'), color: 'neutral', icon: 'i-lucide-log-out' })
    await navigateTo(localePath('/app'))
    return
  }
  await refreshMembers()
}

// ── Invitations ──────────────────────────────────────────────────────────
const invite = reactive({ role: 'worker' as Role, valid_days: 7 as 1 | 7 | 30, email: '' })
const validityItems = computed(() => ([1, 7, 30] as const).map(days => ({ label: t('app.farm.validDays', days), value: days })))
const creatingInvite = ref(false)
const createdLink = ref<string | null>(null)

async function createInvitation() {
  creatingInvite.value = true
  const { data, error } = await api.POST('/api/farms/{farm_id}/invitations', {
    params: { path: path.value },
    body: {
      role: invite.role,
      valid_days: invite.valid_days,
      email: invite.email.trim() || null,
      locale: locale.value === 'en' ? 'en' : 'de'
    }
  })
  creatingInvite.value = false
  if (!data) return failed(error)
  createdLink.value = data.url
  invite.email = ''
  if (data.emailed) toast.add({ title: t('app.farm.inviteEmailed'), color: 'success', icon: 'i-lucide-mail-check' })
  await refreshInvitations()
}

async function copyLink() {
  if (!createdLink.value) return
  await navigator.clipboard.writeText(createdLink.value)
  toast.add({ title: t('app.farm.copied'), color: 'success', icon: 'i-lucide-clipboard-check' })
}

async function revoke(id: string) {
  const { response, error } = await api.DELETE('/api/farms/{farm_id}/invitations/{invitation_id}', {
    params: { path: { ...path.value, invitation_id: id } }
  })
  if (response.status !== 204) return failed(error)
  await refreshInvitations()
}

// ── Danger zone ──────────────────────────────────────────────────────────
const confirmName = ref('')
async function deleteFarm() {
  const { response, error } = await api.DELETE('/api/farms/{farm_id}', {
    params: { path: path.value, query: { confirm: confirmName.value } }
  })
  if (response.status !== 204) return failed(error)
  confirmName.value = ''
  await refreshMe()
  toast.add({ title: t('app.farm.deleted'), color: 'neutral', icon: 'i-lucide-trash-2' })
  await navigateTo(localePath('/app'))
}
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-8">
    <h1 class="text-3xl font-semibold text-highlighted">
      {{ t('app.farm.title') }}
    </h1>

    <UAlert
      v-if="!farm"
      color="neutral"
      variant="subtle"
      icon="i-lucide-tractor"
      :description="t('app.farm.noneLead')"
    />

    <template v-else-if="details">
      <UCard>
        <h2 class="text-lg font-semibold text-highlighted">
          {{ t('app.farm.masterData') }}
        </h2>
        <UForm
          :schema="masterSchema"
          :state="master"
          :disabled="!isAdmin"
          class="mt-4 space-y-4"
          @submit="saveMaster"
        >
          <UFormField
            :label="t('app.fields.farmName')"
            name="name"
          >
            <UInput
              v-model="master.name"
              class="w-full"
            />
          </UFormField>
          <UFormField
            v-if="isAdmin"
            :label="t('app.farm.amaNumber')"
            :help="t('app.farm.amaNumberHelp')"
            name="ama_farm_number"
          >
            <UInput
              v-model="master.ama_farm_number"
              inputmode="numeric"
              class="w-full sm:w-48"
            />
          </UFormField>
          <UButton
            v-if="isAdmin"
            type="submit"
            :loading="savingMaster"
            :label="t('app.tasks.save')"
          />
        </UForm>
      </UCard>

      <UCard>
        <h2 class="text-lg font-semibold text-highlighted">
          {{ t('app.farm.members') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('app.farm.rolesLead') }}
        </p>
        <ul class="mt-4 divide-y divide-default">
          <li
            v-for="member in members"
            :key="member.user.id"
            class="flex flex-wrap items-center gap-3 py-3"
            data-testid="member-row"
          >
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-medium text-highlighted">
                {{ member.user.email }}
                <span
                  v-if="member.user.id === me?.user.id"
                  class="font-normal text-muted"
                >({{ t('app.farm.you') }})</span>
              </span>
              <span class="text-xs text-muted">{{ t('app.farm.joined', { date: day(member.joined_at.slice(0, 10)) }) }}</span>
            </span>
            <USelect
              v-if="isAdmin"
              :model-value="member.role"
              :items="roleItems"
              size="sm"
              class="w-36"
              :aria-label="t('app.farm.role')"
              @update:model-value="(role: Role) => changeRole(member.user.id, role)"
            />
            <UBadge
              v-else
              color="neutral"
              variant="subtle"
              :label="t(`app.roles.${member.role}`)"
            />
            <UButton
              v-if="(isAdmin || member.user.id === me?.user.id) && (members?.length ?? 0) > 1"
              color="neutral"
              variant="ghost"
              size="sm"
              :icon="member.user.id === me?.user.id ? 'i-lucide-log-out' : 'i-lucide-user-minus'"
              :aria-label="member.user.id === me?.user.id ? t('app.farm.leave') : t('app.farm.remove')"
              @click="removing = member"
            />
          </li>
        </ul>
      </UCard>

      <UCard v-if="isAdmin">
        <h2 class="text-lg font-semibold text-highlighted">
          {{ t('app.farm.invitations') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('app.farm.invitationsLead') }}
        </p>
        <div class="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <UFormField :label="t('app.farm.role')">
            <USelect
              v-model="invite.role"
              :items="roleItems"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('app.farm.validity')">
            <USelect
              v-model="invite.valid_days"
              :items="validityItems"
              class="w-full"
            />
          </UFormField>
          <UButton
            icon="i-lucide-link"
            :loading="creatingInvite"
            :label="t('app.farm.createInvite')"
            data-testid="create-invitation"
            @click="createInvitation"
          />
        </div>
        <UFormField
          v-if="config?.password_reset_by_email"
          class="mt-3"
          :label="t('app.farm.inviteEmail')"
          :help="t('app.farm.inviteEmailHelp')"
        >
          <UInput
            v-model="invite.email"
            type="email"
            class="w-full"
          />
        </UFormField>

        <UAlert
          v-if="createdLink"
          class="mt-4"
          color="success"
          variant="subtle"
          icon="i-lucide-link"
          :title="t('app.farm.linkTitle')"
          :description="t('app.farm.linkOnce')"
        >
          <template #actions>
            <div class="flex w-full flex-col gap-2 sm:flex-row">
              <UInput
                :model-value="createdLink"
                readonly
                class="w-full"
                data-testid="invitation-link"
                @focus="($event.target as HTMLInputElement).select()"
              />
              <UButton
                icon="i-lucide-clipboard"
                :label="t('app.farm.copy')"
                @click="copyLink"
              />
            </div>
          </template>
        </UAlert>

        <ul
          v-if="invitations?.length"
          class="mt-4 divide-y divide-default border-t border-default"
        >
          <li
            v-for="invitation in invitations"
            :key="invitation.id"
            class="flex items-center gap-3 py-2.5 text-sm"
          >
            <UBadge
              color="neutral"
              variant="subtle"
              :label="t(`app.roles.${invitation.role}`)"
            />
            <span class="min-w-0 flex-1 truncate text-muted">
              <template v-if="invitation.email">{{ invitation.email }} · </template>
              <span :class="{ 'text-error': invitation.state === 'expired' }">
                {{ invitation.state === 'expired'
                  ? t('app.farm.expired')
                  : t('app.farm.validUntil', { date: moment(invitation.expires_at) }) }}
              </span>
            </span>
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              icon="i-lucide-x"
              :label="t('app.farm.revoke')"
              @click="revoke(invitation.id)"
            />
          </li>
        </ul>
      </UCard>

      <UCard
        v-if="isAdmin"
        class="ring-error/40"
      >
        <h2 class="text-lg font-semibold text-error">
          {{ t('app.farm.dangerZone') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('app.farm.deleteLead') }}
        </p>
        <div class="mt-4 flex flex-col gap-2 sm:flex-row">
          <UInput
            v-model="confirmName"
            :placeholder="details.name"
            :aria-label="t('app.farm.typeName')"
            class="w-full sm:w-72"
          />
          <UButton
            color="error"
            icon="i-lucide-trash-2"
            :disabled="confirmName.trim() !== details.name"
            :label="t('app.farm.delete')"
            @click="deleteFarm"
          />
        </div>
      </UCard>
    </template>

    <UModal
      :open="removing !== null"
      :title="removing?.user.id === me?.user.id ? t('app.farm.leaveTitle') : t('app.farm.removeTitle')"
      :description="removing?.user.id === me?.user.id
        ? t('app.farm.leaveLead', { farm: details?.name ?? '' })
        : t('app.farm.removeLead', { email: removing?.user.email ?? '' })"
      @update:open="(open: boolean) => { if (!open) removing = null }"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('app.tasks.cancel')"
            @click="removing = null"
          />
          <UButton
            color="error"
            :label="removing?.user.id === me?.user.id ? t('app.farm.leave') : t('app.farm.remove')"
            data-testid="confirm-remove"
            @click="removeMember"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>
