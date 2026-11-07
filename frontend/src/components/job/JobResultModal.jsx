import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuCircleAlert, LuCircleCheck, LuCircleX, LuInfo, LuRotateCcw } from 'react-icons/lu'
import { useNavigate } from 'react-router-dom'
import { useJob } from '../../hooks/useJob'
import { displayId } from '../../lib/format'
import { startErrorCode, summarizeJob } from '../../lib/jobResult'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

const OUTCOME_STYLE = {
  success: { icon: LuCircleCheck, tone: 'text-brand-text' },
  partial: { icon: LuCircleAlert, tone: 'text-warn-text' },
  failed: { icon: LuCircleX, tone: 'text-danger-text' },
  empty: { icon: LuInfo, tone: 'text-info-text' },
}

function Reasons({ groups, showCount }) {
  const { t, i18n } = useTranslation()
  return (
    <ul className="space-y-2">
      {groups.map(({ code, count }) => {
        const key = i18n.exists(`jobError.${code}.title`) ? code : 'internal'
        return (
          <li key={code} className="rounded-xl bg-surface-muted p-3 text-sm">
            <p className="font-medium">
              {t(`jobError.${key}.title`)}
              {showCount && count > 1 && ` (${count})`}
            </p>
            <p className="mt-0.5 text-ink-muted">{t(`jobError.${key}.action`)}</p>
          </li>
        )
      })}
    </ul>
  )
}

function TechnicalDetails({ lines }) {
  const { t } = useTranslation()
  if (!lines.length) return null
  return (
    <details className="text-xs text-ink-muted">
      <summary className="cursor-pointer">{t('job.result.details')}</summary>
      <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto break-words">
        {lines.map((line, index) => (
          <li key={index}>{line}</li>
        ))}
      </ul>
    </details>
  )
}

function FinishedResult({ job, onClose, onRetry }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const summary = summarizeJob(job)
  const { outcome, done, failed, failedGroups, skippedGroups } = summary
  const { icon: Icon, tone } = OUTCOME_STYLE[outcome]

  const openResults = () => {
    onClose()
    navigate(done === 1 ? `/dialogs/${encodeURIComponent(job.done[0].conversation_id)}` : '/dialogs')
  }

  return (
    <Modal open onClose={onClose} title={t(`job.result.${outcome}.title`)} description={t(`job.result.${outcome}.text`, { done, failed })}>
      <div className="space-y-4">
        <Icon className={clsx('mx-auto size-12', tone)} aria-hidden />
        {failedGroups.length > 0 && <Reasons groups={failedGroups} showCount />}
        {skippedGroups.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-ink-muted">{t('job.result.skipped', { count: job.skipped.length })}</p>
            <Reasons groups={skippedGroups} />
          </div>
        )}
        <TechnicalDetails lines={[...job.failed, ...job.skipped].map((item) => `${displayId(item.conversation_id)}: ${item.reason}`)} />
        <div className="flex flex-wrap justify-end gap-2">
          {failed > 0 && (
            <Button icon={LuRotateCcw} onClick={() => onRetry(job)}>
              {t(done ? 'job.result.retryFailed' : 'job.result.retry')}
            </Button>
          )}
          {done > 0 ? (
            <Button variant="primary" onClick={openResults}>
              {t('job.result.view')}
            </Button>
          ) : (
            <Button onClick={onClose}>{t('common.close')}</Button>
          )}
        </div>
      </div>
    </Modal>
  )
}

function StartFailure({ error, onClose }) {
  const { t } = useTranslation()
  const code = startErrorCode(error)
  return (
    <Modal open onClose={onClose} title={t('job.result.failed.title')} description={t('job.result.notStarted')}>
      <div className="space-y-4">
        <LuCircleX className="mx-auto size-12 text-danger-text" aria-hidden />
        <Reasons groups={[{ code, count: 1 }]} />
        <TechnicalDetails lines={error.detail ? [error.detail] : []} />
        <div className="flex justify-end">
          <Button onClick={onClose}>{t('common.close')}</Button>
        </div>
      </div>
    </Modal>
  )
}

export default function JobResultModal() {
  const { result, startError, acknowledge, start } = useJob()
  if (startError) return <StartFailure error={startError} onClose={acknowledge} />
  if (!result) return null

  const retry = (job) => {
    acknowledge()
    start({ mode: job.kind, conversationIds: job.failed.map((item) => item.conversation_id) })
  }
  return <FinishedResult job={result} onClose={acknowledge} onRetry={retry} />
}
