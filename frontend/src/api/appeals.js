import { request } from './client'

export const fetchAppeals = () => request('/appeals')

export const createAppeal = ({ evaluationId, criterionId, comment }) =>
  request(`/evaluations/${evaluationId}/appeals`, {
    method: 'POST',
    json: { criterion_id: criterionId, comment },
  })

export const resolveAppeal = ({ appealId, decision, reason, value, na }) =>
  request(`/appeals/${appealId}/resolve`, { method: 'POST', json: { decision, reason, value, na } })
