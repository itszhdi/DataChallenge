import { request } from './client'

export const evaluateConversation = (conversationId) =>
  request('/evaluate', { method: 'POST', json: { conversation_id: conversationId } })

export const startBatch = ({ dataset, mode, onlyMissing }) =>
  request('/evaluate/batch', { method: 'POST', json: { dataset: dataset || null, mode, only_missing: onlyMissing } })

export const fetchJob = (id) => request(`/jobs/${id}`)

export const fetchEvaluation = (id) => request(`/evaluations/${id}`)

export const reapplyEvaluation = (id) => request(`/evaluations/${id}/reapply`, { method: 'POST' })
