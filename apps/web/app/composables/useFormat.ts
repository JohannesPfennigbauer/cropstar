/** Locale-aware number formatting for the farm app. */
export function useFormat() {
  const { locale } = useI18n()

  function hectares(value: number, digits = 2): string {
    const number = new Intl.NumberFormat(locale.value === 'en' ? 'en-GB' : 'de-AT', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    }).format(value)
    return `${number} ha`
  }

  return { hectares }
}
