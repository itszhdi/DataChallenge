const STATUS_BY_API_ERROR = { 0: 'backend_down', 409: 'job_running' }

function groupByCode(items) {
  const counts = new Map()
  items.forEach(({ code }) => counts.set(code, (counts.get(code) ?? 0) + 1))
  return [...counts].map(([code, count]) => ({ code, count }))
}

export function summarizeJob(job) {
  const done = job.done.length
  const failed = job.failed.length
  let outcome = 'empty'
  if (failed) outcome = done ? 'partial' : 'failed'
  else if (done) outcome = 'success'
  return { outcome, done, failed, failedGroups: groupByCode(job.failed), skippedGroups: groupByCode(job.skipped) }
}

export const startErrorCode = (error) => error.code ?? STATUS_BY_API_ERROR[error.status] ?? 'internal'

// Статус диалога в идущей задаче: id → analyzing | queued
export function liveStatuses(job) {
  if (job?.status !== 'running') return new Map()
  const finished = new Set([...job.done, ...job.failed, ...job.skipped].map((item) => item.conversation_id))
  return new Map(
    job.conversation_ids
      .filter((id) => !finished.has(id))
      .map((id) => [id, job.current.includes(id) ? 'analyzing' : 'queued']),
  )
}
