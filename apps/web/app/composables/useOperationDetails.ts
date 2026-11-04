import type { ChoiceField, OperationDetails } from '~/utils/operation-details'
import { DETAIL_FIELDS } from '~/utils/operation-details'

type Values = Record<string, unknown>

/** Details in one readable line, e.g. "Grubber · 8 cm · nass". */
export function useOperationDetails() {
  const { t } = useI18n()
  const { decimal } = useFormat()

  function choice(details: Values, field: ChoiceField): string | null {
    const value = details[field.key]
    return typeof value === 'string' ? t(`app.details.values.${field.group}.${value}`) : null
  }

  function summary(details: OperationDetails | null | undefined): string {
    if (!details) return ''
    const values = details as Values
    const parts: string[] = []
    for (const field of DETAIL_FIELDS[details.type] ?? []) {
      const value = values[field.key]
      if (field.kind === 'choice') {
        // Units are shown with their amount instead.
        const isUnit = DETAIL_FIELDS[details.type].some(f => f.kind === 'number' && f.unitKey === field.key)
        const text = isUnit ? null : choice(values, field)
        if (text) parts.push(text)
        continue
      }
      if (typeof value !== 'number') continue
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

  return { summary }
}
