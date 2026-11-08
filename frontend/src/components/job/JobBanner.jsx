import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuCirclePause, LuLoaderCircle, LuPause, LuPlay, LuSquare } from 'react-icons/lu'
import { useJob } from '../../hooks/useJob'
import { useNow } from '../../hooks/useNow'
import { displayId, formatClock } from '../../lib/format'
import Button from '../ui/Button'
import ProgressBar from '../ui/ProgressBar'

const MS_IN_SECOND = 1000

function timing(job, now) {
  const elapsed = Math.max(0, (now - Date.parse(job.created_at)) / MS_IN_SECOND)
  const finished = job.done.length + job.failed.length
  const left = job.total - job.processed
  return { elapsed, remaining: finished && left ? (elapsed / finished) * left : null }
}

// Подпись под прогрессом: что делается сейчас и что будет по кнопкам
function stateLine(job, t) {
  if (job.stopped) return t('job.stopping')
  if (job.status === 'paused') return t('job.pausedHint')
  return job.current.length ? t('job.current', { ids: job.current.map(displayId).join(', ') }) : t('job.waiting')
}

export default function JobBanner() {
  const { t } = useTranslation()
  const { job, control, isControlling } = useJob()
  const isActive = job?.status === 'running' || job?.status === 'paused'
  const isPaused = job?.status === 'paused'
  const now = useNow(isActive && !isPaused)
  if (!isActive) return null

  const { elapsed, remaining } = timing(job, now)
  const label = t(job.kind === 'reapply' ? 'job.reapply' : 'job.evaluate')
  const StateIcon = isPaused ? LuCirclePause : LuLoaderCircle
  return (
    <section
      aria-live="polite"
      aria-label={label}
      className="sticky top-16 z-20 border-b border-line bg-surface px-4 py-3 sm:px-6 lg:px-8"
    >
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <StateIcon className={clsx('size-4 shrink-0', isPaused ? 'text-warn-text' : 'animate-spin text-brand-text')} />
        <b>{label}</b>
        {isPaused && <span className="text-warn-text">{t('job.paused')}</span>}
        <span className="text-ink-muted tabular-nums">{t('job.counter', { processed: job.processed, total: job.total })}</span>
        {job.failed.length > 0 && <span className="text-danger-text">{t('job.failedCount', { count: job.failed.length })}</span>}
        <span className="text-xs text-ink-muted tabular-nums sm:ml-auto">
          {t('job.elapsed', { time: formatClock(elapsed) })}
          {!isPaused && remaining !== null && ` · ${t('job.remaining', { time: formatClock(remaining) })}`}
        </span>
        <div className="flex gap-2">
          {isPaused ? (
            <Button size="sm" variant="primary" icon={LuPlay} disabled={isControlling || job.stopped} onClick={() => control('resume')}>
              {t('job.resume')}
            </Button>
          ) : (
            <Button size="sm" icon={LuPause} disabled={isControlling || job.stopped} onClick={() => control('pause')}>
              {t('job.pause')}
            </Button>
          )}
          <Button size="sm" icon={LuSquare} loading={job.stopped} disabled={isControlling} onClick={() => control('stop')}>
            {t('job.stop')}
          </Button>
        </div>
      </div>
      <ProgressBar
        label={label}
        value={(job.processed / job.total) * 100}
        indeterminate={job.processed === 0 && !isPaused}
        tone={isPaused || job.failed.length ? 'warning' : 'success'}
      />
      <p className="mt-1.5 truncate text-xs text-ink-muted">{stateLine(job, t)}</p>
    </section>
  )
}
