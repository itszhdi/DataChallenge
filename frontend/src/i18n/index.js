import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import { STORAGE_KEYS } from '../lib/constants'
import en from './locales/en.json'
import kz from './locales/kz.json'
import ru from './locales/ru.json'

export const UI_LANGUAGES = [
  { code: 'en', label: 'EN', locale: 'en-GB' },
  { code: 'kk', label: 'KZ', locale: 'kk-KZ' },
  { code: 'ru', label: 'RU', locale: 'ru-RU' },
]

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, kk: { translation: kz }, ru: { translation: ru } },
    fallbackLng: 'ru',
    supportedLngs: UI_LANGUAGES.map((language) => language.code),
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: { order: ['localStorage', 'navigator'], lookupLocalStorage: STORAGE_KEYS.language, caches: ['localStorage'] },
  })

const syncHtmlLang = (language) => {
  document.documentElement.lang = language
}
syncHtmlLang(i18n.resolvedLanguage)
i18n.on('languageChanged', syncHtmlLang)

export default i18n
