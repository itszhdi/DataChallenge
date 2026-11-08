import { buildUrl, request } from './client'

// Файл для сдачи организаторам (формат JSON 1.0): target dev | prod, без target бэкенд выбирает папку по набору
const submissionParams = ({ dataset, target }) => ({ dataset, target })

export const previewSubmission = (options) => request('/export/submission', { params: submissionParams(options) })

// Файл отдаёт бэкенд с Content-Disposition: браузер скачивает results.json сам
export const submissionDownloadUrl = (options) => buildUrl('/export/submission', { ...submissionParams(options), download: true })

export const saveSubmission = (options) => request('/export/submission/save', { method: 'POST', params: submissionParams(options) })
