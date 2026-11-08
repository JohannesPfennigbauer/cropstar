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

  /** A measured value as entered, with at most two decimals: "6,25". */
  function decimal(value: number): string {
    return new Intl.NumberFormat(intlLocale(), { maximumFractionDigits: 2 }).format(value)
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

  /** A calendar date in compact numeric form: "20.03.27". */
  function shortDay(value: string): string {
    const [year, month, date] = value.split('-').map(Number)
    return new Intl.DateTimeFormat(intlLocale(), { day: '2-digit', month: '2-digit', year: '2-digit', timeZone: 'UTC' })
      .format(new Date(Date.UTC(year!, month! - 1, date!)))
  }

  function moment(value: string): string {
    return new Intl.DateTimeFormat(intlLocale(), { dateStyle: 'medium', timeStyle: 'short' })
      .format(new Date(value))
  }

  return { hectares, decimal, day, shortDay, moment }
}
