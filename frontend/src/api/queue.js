import { request } from './client'

export const fetchQueue = (dataset) => request('/queue', { params: { dataset } })

// Выключает автопроверку и прерывает диалог, который она сейчас анализирует
export const stopWorker = () => request('/worker/stop', { method: 'POST' })
