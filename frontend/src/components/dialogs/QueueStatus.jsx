import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuBot, LuRotateCcw, LuSquare } from 'react-icons/lu'
import { toast } from 'sonner'
import { stopWorker } from '../../api/queue'
import { displayId, formatClock } from '../../lib/format'
import Button from '../ui/Button'

function workerText(worker, t) {
  if (worker.status === 'error') return t('queue.worker.error', { error: worker.last_error ?? worker.reason })
  if (worker.mode !== 'auto') return t('queue.worker.manual')
  // Между диалогами воркер на миг остаётся running без current — показываем общее «работает»
  if (worker.status === 'running') return worker.current ? t('queue.worker.running', { id: displayId(worker.current) }) : t('queue.worker.active')
  if (worker.status === 'paused') return t('queue.worker.paused')
  return t('queue.worker.idle')
}

// Строка над списком: что анализируется сейчас, сколько ждёт, состояние автопроверки и повтор упавших
export default function QueueStatus({ queue, isBusy, onRetryFailed }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  // Остановка автопроверки: выключает авторежим и прерывает текущий диалог
  const stop = useMutation({
    mutationFn: stopWorker,
    onSuccess: () => {
      toast.success(t('queue.stopped'))
      queryClient.invalidateQueries({ predicate: ({ queryKey }) => queryKey[0] === 'queue' || queryKey[0] === 'settings' })
    },
    onError: (error) => toast.error(error.detail || t('job.controlFailed')),
  })
  if (!queue) return null
  const { counts, worker, model } = queue
  const waiting = counts.queued + counts.upcoming
  const isActive = counts.running + waiting > 0

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-4 py-3 text-sm">
      {isActive && (
        <span className="tabular-nums">
          {t('queue.summary', { running: counts.running, waiting })}
          {queue.eta_total_sec > 0 && ` · ~${formatClock(queue.eta_total_sec)}`}
          <span className="text-ink-muted"> · {model.name}</span>
        </span>
      )}
      <span className={clsx('inline-flex items-center gap-1.5 text-xs', worker.status === 'error' ? 'text-danger-text' : 'text-ink-muted')}>
        <LuBot className="size-4 shrink-0" />
        {workerText(worker, t)}
      </span>
      {worker.auto_mode && (
        <Button size="sm" icon={LuSquare} loading={stop.isPending} onClick={() => stop.mutate()}>
          {t('queue.stopAuto')}
        </Button>
      )}
      {counts.failed > 0 && (
        <Button size="sm" icon={LuRotateCcw} disabled={isBusy} onClick={onRetryFailed} className="sm:ml-auto">
          {t('queue.retryFailed', { count: counts.failed })}
        </Button>
      )}
    </div>
  )
}
