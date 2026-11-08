import { useTranslation } from 'react-i18next'
import { LuRefreshCw, LuTriangleAlert } from 'react-icons/lu'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom'
import { isChunkError } from '../../lib/chunkReload'
import Button from '../ui/Button'
import { Card } from '../ui/Card'

// Ошибка страницы показывается внутри приложения: навбар и меню остаются, есть понятный выход
export default function RouteError() {
  const { t } = useTranslation()
  const error = useRouteError()
  const isNewVersion = isChunkError(error)
  const detail = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : String(error?.message ?? error)

  return (
    <Card className="mx-auto max-w-xl p-8 text-center">
      <LuTriangleAlert className="mx-auto size-10 text-warn-text" aria-hidden />
      <h1 className="mt-3 text-lg font-semibold">{t(isNewVersion ? 'routeError.newVersionTitle' : 'routeError.title')}</h1>
      <p className="mt-2 text-sm text-ink-muted">{t(isNewVersion ? 'routeError.newVersionText' : 'routeError.text')}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Button variant="primary" icon={LuRefreshCw} onClick={() => window.location.reload()}>
          {t('routeError.reload')}
        </Button>
        <Link to="/" className="inline-flex h-10 items-center rounded-lg border border-line px-4 text-sm font-medium hover:bg-surface-muted">
          {t('routeError.home')}
        </Link>
      </div>
      <details className="mt-5 text-left text-xs text-ink-muted">
        <summary className="cursor-pointer">{t('job.result.details')}</summary>
        <p className="mt-2 break-words">{detail}</p>
      </details>
    </Card>
  )
}
