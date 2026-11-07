import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { fetchJob, startBatch } from '../api/evaluations'
import { JOB_POLL_MS, STORAGE_KEYS } from '../lib/constants'
import { useApiError } from './useApiError'

const readStoredJobId = () => sessionStorage.getItem(STORAGE_KEYS.jobId)

// Задача живёт в памяти бэкенда; её id хранится в сессии, чтобы прогресс пережил перезагрузку страницы
export function useBatchJob() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { notify } = useApiError()
  const [jobId, setJobId] = useState(readStoredJobId)
  const announcedJobId = useRef(null)

  const job = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId),
    enabled: Boolean(jobId),
    retry: false,
    refetchInterval: (query) => (query.state.data?.status === 'finished' ? false : JOB_POLL_MS),
  })

  const rememberJob = (id) => {
    if (id) sessionStorage.setItem(STORAGE_KEYS.jobId, id)
    else sessionStorage.removeItem(STORAGE_KEYS.jobId)
    setJobId(id)
  }

  const start = useMutation({
    mutationFn: startBatch,
    onSuccess: (created) => rememberJob(created.id),
    onError: notify,
  })

  const finishedJob = job.data?.status === 'finished' ? job.data : null
  useEffect(() => {
    if (!finishedJob || announcedJobId.current === finishedJob.id) return
    announcedJobId.current = finishedJob.id
    queryClient.invalidateQueries({ queryKey: ['conversations'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    toast.success(
      t('job.finished', {
        done: finishedJob.done.length,
        skipped: finishedJob.skipped.length,
        failed: finishedJob.failed.length,
      }),
    )
  }, [finishedJob, queryClient, t])

  return {
    job: job.data ?? null,
    isRunning: start.isPending || (Boolean(jobId) && job.data?.status !== 'finished' && !job.isError),
    start: start.mutate,
    dismiss: () => rememberJob(null),
  }
}
