import { useTranslation } from 'react-i18next'
import { LuInbox, LuLoaderCircle, LuTriangleAlert } from 'react-icons/lu'
import { useApiError } from '../../hooks/useApiError'
import Button from './Button'

export function EmptyState({ title, description, children }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <LuInbox className="size-8 text-ink-muted" />
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-md text-sm text-ink-muted">{description}</p>}
      {children}
    </div>
  )
}

export function LoadingState() {
  const { t } = useTranslation()
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-ink-muted">
      <LuLoaderCircle className="size-5 animate-spin" />
      {t('common.loading')}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  const { t } = useTranslation()
  const { describe } = useApiError()
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <LuTriangleAlert className="size-8 text-danger" />
      <p className="max-w-md text-sm">{describe(error)}</p>
      {onRetry && <Button onClick={onRetry}>{t('common.retry')}</Button>}
    </div>
  )
}
