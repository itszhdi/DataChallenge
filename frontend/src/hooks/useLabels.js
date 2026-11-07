import { useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'

// Перевод стандартных названий чек-листа. Изменённое название показывается как есть,
// поэтому заменённый критерий с тем же id не получит устаревший перевод
export function useLabels() {
  const { t, i18n } = useTranslation()
  const translate = useCallback(
    (kind, id, title) => {
      const key = `checklist.${kind}.${id}`
      const original = i18n.getFixedT('ru')(key, { defaultValue: '' })
      return original && original === title ? t(key) : title
    },
    [t, i18n],
  )
  return useMemo(
    () => ({
      criterion: (id, title) => translate('criteria', id, title),
      section: (id, title) => translate('sections', id, title),
    }),
    [translate],
  )
}
