import { request } from './client'

export const fetchQueue = (dataset) => request('/queue', { params: { dataset } })
