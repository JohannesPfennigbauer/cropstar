import type { Schemas } from '@cropstar/api-client'
import type { ChoiceField, OperationDetails } from '~/utils/operation-details'
import { DETAIL_FIELDS } from '~/utils/operation-details'

type Values = Record<string, unknown>
type AppliedInput = Schemas['AppliedInput']

/** Details in one readable line, e.g. "Grubber · 8 cm · nass". */
export function useOperationDetails() {
  const { t } = useI18n()
  const { decimal, day } = useFormat()

  function choice(details: Values, field: ChoiceField): string | null {
    const value = details[field.key]
    return typeof value === 'string' ? t(`app.details.values.${field.group}.${value}`) : null
  }

  /** `applied` names the Farm Input the details refer to, archived or not. */
  function summary(details: OperationDetails | null | undefined, applied?: AppliedInput | null): string {
    if (!details) return ''
    const values = details as Values
    const parts: string[] = []
    if (applied) parts.push(applied.farm_input.name)
    for (const field of DETAIL_FIELDS[details.type] ?? []) {
      const value = values[field.key]
      if (field.kind === 'choice') {
        // Units are shown with their amount instead.
        const isUnit = DETAIL_FIELDS[details.type].some(f => f.kind === 'number' && f.unitKey === field.key)
        const text = isUnit ? null : choice(values, field)
        if (text) parts.push(text)
        continue
      }
      if (field.kind !== 'number' || typeof value !== 'number') continue
      if (field.unitKey) {
        const unit = values[field.unitKey]
        const group = (DETAIL_FIELDS[details.type].find(f => f.key === field.unitKey) as ChoiceField).group
        parts.push(`${decimal(value)} ${typeof unit === 'string' ? t(`app.details.values.${group}.${unit}`) : ''}`.trim())
      }
      else {
        parts.push(t(`app.details.summary.${field.key}`, { n: decimal(value) }))
      }
    }
    if (details.note) parts.push(details.note)
    return parts.join(' · ')
  }

  /** "≙ 63,2 kg N (38,5 jahreswirksam) · 25 kg P₂O₅ · 124,9 kg K₂O je ha". */
  function nutrients(applied: AppliedInput | null | undefined): string {
    const n = applied?.nutrients
    if (!n) return ''
    const parts: string[] = []
    if (n.total_n !== null) {
      const available = n.available_n !== null ? ` ${t('app.farmInputs.availableShort', { n: decimal(n.available_n) })}` : ''
      parts.push(`${decimal(n.total_n)} kg N${available}`)
    }
    if (n.p2o5 !== null) parts.push(`${decimal(n.p2o5)} kg P₂O₅`)
    if (n.k2o !== null) parts.push(`${decimal(n.k2o)} kg K₂O`)
    return parts.length ? t('app.details.nutrientsApplied', { nutrients: parts.join(' · ') }) : ''
  }

  /** Where the contents behind `nutrients` come from, e.g. "Laboranalyse 2. März 2026 · Labor X". */
  function nutrientSource(applied: AppliedInput | null | undefined): string {
    const n = applied?.nutrients
    if (!n?.value_source) return ''
    const when = n.analysed_on ? ` ${day(n.analysed_on)}` : ''
    return [`${t(`app.farmInputs.sources.${n.value_source}`)}${when}`, n.source_reference].filter(Boolean).join(' · ')
  }

  return { summary, nutrients, nutrientSource }
}
