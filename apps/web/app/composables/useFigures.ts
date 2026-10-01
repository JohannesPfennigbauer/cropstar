/** Locale-aware number formatting; German needs comma decimals. */
export function useFigures() {
  const { locale, locales } = useI18n()

  const tag = computed(() => {
    const active = (locales.value as Array<{ code: string, language?: string }>)
      .find(entry => entry.code === locale.value)
    return active?.language ?? locale.value
  })

  function format(value: number, precision: number): string {
    return new Intl.NumberFormat(tag.value, {
      minimumFractionDigits: precision,
      maximumFractionDigits: precision
    }).format(value)
  }

  function withUnit(value: number, precision: number, unit: string): string {
    return unit ? `${format(value, precision)} ${unit}` : format(value, precision)
  }

  // Content dates are calendar days stored as UTC midnight.
  function formatDate(value: string | Date): string {
    return new Intl.DateTimeFormat(tag.value, { dateStyle: 'long', timeZone: 'UTC' }).format(new Date(value))
  }

  return { format, withUnit, formatDate }
}
