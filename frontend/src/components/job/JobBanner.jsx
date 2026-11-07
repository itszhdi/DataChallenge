import { useTranslation } from 'react-i18next'
import { LuLoaderCircle } from 'react-icons/lu'
import { useJob } from '../../hooks/useJob'
import { useNow } from '../../hooks/useNow'
import { displayId, formatClock } from '../../lib/format'
import ProgressBar from '../ui/ProgressBar'

const MS_IN_SECOND = 1000

function timing(job, now) {
  const elapsed = Math.max(0, (now - Date.parse(job.created_at)) / MS_IN_SECOND)
  const finished = job.done.length + job.failed.length
  const left = job.total - job.processed
  return { elapsed, remaining: finished && left ? (elapsed / finished) * left : null }
}

export default function JobBanner() {
  const { t } = useTranslation()
  const { job } = useJob()
  const isRunning = job?.status === 'running'
  const now = useNow(isRunning)
  if (!isRunning) return null

  const { elapsed, remaining } = timing(job, now)
  const label = t(job.kind === 'reapply' ? 'job.reapply' : 'job.evaluate')
  return (
    <section
      aria-live="polite"
      aria-label={label}
      className="sticky top-16 z-20 border-b border-line bg-surface px-4 py-3 sm:px-6 lg:px-8"
    >
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <LuLoaderCircle className="size-4 shrink-0 animate-spin text-brand-text" />
        <b>{label}</b>
        <span className="text-ink-muted tabular-nums">{t('job.counter', { processed: job.processed, total: job.total })}</span>
        {job.failed.length > 0 && <span className="text-danger-text">{t('job.failedCount', { count: job.failed.length })}</span>}
        <span className="text-xs text-ink-muted tabular-nums sm:ml-auto">
          {t('job.elapsed', { time: formatClock(elapsed) })}
          {remaining !== null && ` · ${t('job.remaining', { time: formatClock(remaining) })}`}
        </span>
      </div>
      <ProgressBar label={label} value={(job.processed / job.total) * 100} indeterminate={job.processed === 0} tone={job.failed.length ? 'warning' : 'success'} />
      <p className="mt-1.5 truncate text-xs text-ink-muted">
        {job.current.length ? t('job.current', { ids: job.current.map(displayId).join(', ') }) : t('job.waiting')}
      </p>
    </section>
  )
}
