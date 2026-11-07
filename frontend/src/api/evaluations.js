import { request } from './client'

export const startBatch = ({ dataset, mode, onlyMissing = false, conversationIds = null }) =>
  request('/evaluate/batch', {
    method: 'POST',
    json: { dataset: dataset || null, mode, only_missing: onlyMissing, conversation_ids: conversationIds },
  })

export const fetchJob = (id) => request(`/jobs/${id}`)

export const fetchEvaluation = (id) => request(`/evaluations/${id}`)
