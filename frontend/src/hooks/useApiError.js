import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

const LOCALIZED_STATUSES = [0, 403, 404, 409, 422, 429, 502]

export function useApiError() {
  const { t } = useTranslation()
  const describe = useCallback(
    (error) => {
      const status = LOCALIZED_STATUSES.includes(error?.status) ? error.status : 'generic'
      const message = t(`errors.${status}`)
      return error?.detail ? `${message}: ${error.detail}` : message
    },
    [t],
  )
  const notify = useCallback((error) => toast.error(describe(error)), [describe])
  return { describe, notify }
}
