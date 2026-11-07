import { useQuery } from '@tanstack/react-query'
import { fetchQueue } from '../api/queue'
import { QUEUE_ACTIVE_POLL_MS, QUEUE_IDLE_POLL_MS } from '../lib/constants'

// Очередь анализа: часто опрашиваем, пока что-то идёт или включён авторежим, иначе редко
export const isQueueActive = (queue) =>
  Boolean(queue && (queue.counts.running + queue.counts.queued + queue.counts.upcoming > 0 || queue.worker.auto_mode))

export const useQueue = (dataset) =>
  useQuery({
    queryKey: ['queue', dataset ?? ''],
    queryFn: () => fetchQueue(dataset),
    refetchInterval: (query) => (isQueueActive(query.state.data) ? QUEUE_ACTIVE_POLL_MS : QUEUE_IDLE_POLL_MS),
  })
