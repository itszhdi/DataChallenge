import { request } from './client'

export const fetchSettings = () => request('/settings')

export const updateSettings = (settings) => request('/settings', { method: 'PUT', json: settings })

export const checkModels = () => request('/settings/models')
