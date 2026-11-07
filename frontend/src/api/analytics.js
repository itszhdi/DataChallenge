import { request } from './client'

export const fetchDashboard = (dataset) => request('/analytics/dashboard', { params: { dataset } })
