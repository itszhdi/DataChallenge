import { request } from './client'

export const startBatch = ({ dataset, mode = 'evaluate', onlyMissing = false, onlyFailed = false, conversationIds = null }) =>
  request('/evaluate/batch', {
    method: 'POST',
    json: { dataset: dataset || null, mode, only_missing: onlyMissing, only_failed: onlyFailed, conversation_ids: conversationIds },
  })

export const fetchJob = (id) => request(`/jobs/${id}`)

export const fetchActiveJobs = () => request('/jobs', { params: { active: true } })

export const fetchEvaluation = (id) => request(`/evaluations/${id}`)
