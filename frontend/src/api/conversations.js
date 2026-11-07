import { buildUrl, request } from './client'

export const fetchConversations = (dataset) => request('/conversations', { params: { dataset } })

export const fetchConversation = (id) => request(`/conversations/${encodeURIComponent(id)}`)

export const audioUrl = (id) => buildUrl(`/audio/${encodeURIComponent(id)}`)
