import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { fetchJob, startBatch } from '../../api/evaluations'
import { JobContext } from '../../hooks/useJob'
import { JOB_POLL_MS, STORAGE_KEYS } from '../../lib/constants'

const readSession = (key) => sessionStorage.getItem(key)

// Единая фоновая задача приложения. Задача живёт на бэкенде, а её id хранится в сессии,
// поэтому прогресс переживает смену страницы и перезагрузку
export default function JobProvider({ children }) {
  const queryClient = useQueryClient()
  const [jobId, setJobId] = useState(() => readSession(STORAGE_KEYS.jobId))
  const [acknowledgedId, setAcknowledgedId] = useState(() => readSession(STORAGE_KEYS.jobAcknowledged))
  const [startError, setStartError] = useState(null)

  const query = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId),
    enabled: Boolean(jobId),
    retry: false,
    refetchInterval: (state) => (state.state.data?.status === 'finished' ? false : JOB_POLL_MS),
  })
  const job = query.data ?? null
  const finishedId = job?.status === 'finished' ? job.id : null

  useEffect(() => {
    if (finishedId) queryClient.invalidateQueries({ predicate: ({ queryKey }) => queryKey[0] !== 'job' })
  }, [finishedId, queryClient])

  const track = (id) => {
    sessionStorage.setItem(STORAGE_KEYS.jobId, id)
    setJobId(id)
  }

  const start = useMutation({
    mutationFn: startBatch,
    onMutate: () => setStartError(null),
    onSuccess: (created) => track(created.id),
    onError: setStartError,
  })

  const isRunning = start.isPending || (Boolean(jobId) && job?.status !== 'finished' && !query.isError)
  const { mutate } = start

  const value = useMemo(
    () => ({
      job,
      isRunning,
      start: mutate,
      track,
      startError,
      result: finishedId && finishedId !== acknowledgedId ? job : null,
      acknowledge: () => {
        setStartError(null)
        if (!finishedId) return
        sessionStorage.setItem(STORAGE_KEYS.jobAcknowledged, finishedId)
        setAcknowledgedId(finishedId)
      },
    }),
    [job, isRunning, mutate, startError, finishedId, acknowledgedId],
  )

  return <JobContext.Provider value={value}>{children}</JobContext.Provider>
}
