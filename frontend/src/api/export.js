import { buildUrl, request } from './client'

const exportParams = ({ dataset, teamName, modelMode, modelName }) => ({
  dataset,
  team_name: teamName,
  model_mode: modelMode,
  model_name: modelName,
})

// Файл отдаёт бэкенд с Content-Disposition: браузер скачивает его сам
export const exportDownloadUrl = (options) => buildUrl('/export', { ...exportParams(options), download: true })

export const saveExport = (options) => request('/export/save', { method: 'POST', params: exportParams(options) })
