import { useTranslation } from 'react-i18next'
import { LuX } from 'react-icons/lu'
import Button from '../ui/Button'
import { Card } from '../ui/Card'
import ProgressBar from '../ui/ProgressBar'

function JobIssues({ title, items }) {
  if (!items.length) return null
  return (
    <details className="mt-2 text-xs text-ink-muted">
      <summary className="cursor-pointer">
        {title} ({items.length})
      </summary>
      <ul className="mt-1 space-y-0.5">
        {items.map((item) => (
          <li key={item.conversation_id}>
            <b>{item.conversation_id}</b>: {item.reason}
          </li>
        ))}
      </ul>
    </details>
  )
}

export default function JobProgress({ job, onDismiss }) {
  const { t } = useTranslation()
  const isRunning = job.status === 'running'
  const percent = job.total ? (job.processed / job.total) * 100 : 100
  return (
    <Card className="mb-4 p-4" aria-live="polite">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <b>{t(job.kind === 'reapply' ? 'job.reapply' : 'job.evaluate')}</b>
        <span className="text-ink-muted">{t(isRunning ? 'job.running' : 'job.finishedShort')}</span>
        <span className="ml-auto text-xs text-ink-muted">
          {t('job.progress', {
            processed: job.processed,
            total: job.total,
            done: job.done.length,
            skipped: job.skipped.length,
            failed: job.failed.length,
          })}
        </span>
        {!isRunning && <Button variant="ghost" size="sm" icon={LuX} aria-label={t('common.close')} onClick={onDismiss} />}
      </div>
      <ProgressBar value={percent} label={t('job.evaluate')} tone={job.failed.length ? 'warning' : 'success'} />
      <JobIssues title={t('job.failed')} items={job.failed} />
      <JobIssues title={t('job.skipped')} items={job.skipped} />
    </Card>
  )
}
