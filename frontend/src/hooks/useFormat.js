import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { UI_LANGUAGES } from '../i18n'

export function useFormat() {
  const { i18n } = useTranslation()
  const locale = UI_LANGUAGES.find((language) => language.code === i18n.resolvedLanguage)?.locale ?? 'ru-RU'
  return useMemo(() => {
    const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 })
    const date = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' })
    return {
      number: (value) => (value === null || value === undefined ? '—' : number.format(value)),
      percent: (value) => (value === null || value === undefined ? '—' : `${number.format(value)}%`),
      date: (value) => (value ? date.format(new Date(value)) : '—'),
    }
  }, [locale])
}
