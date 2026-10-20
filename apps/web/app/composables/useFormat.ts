/** Locale-aware number formatting for the farm app. */
export function useFormat() {
  const { locale } = useI18n()

  function hectares(value: number, digits = 2): string {
    const number = new Intl.NumberFormat(intlLocale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    }).format(value)
    return `${number} ha`
  }

  function intlLocale(): string {
    return locale.value === 'en' ? 'en-GB' : 'de-AT'
  }

  /** A calendar date from the API ("2027-03-20"), without shifting it through time zones. */
  function day(value: string): string {
    const [year, month, date] = value.split('-').map(Number)
    return new Intl.DateTimeFormat(intlLocale(), { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
      .format(new Date(Date.UTC(year!, month! - 1, date!)))
  }

  function moment(value: string): string {
    return new Intl.DateTimeFormat(intlLocale(), { dateStyle: 'medium', timeStyle: 'short' })
      .format(new Date(value))
  }

  return { hectares, day, moment }
}
