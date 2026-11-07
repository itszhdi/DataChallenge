import { request } from './client'

export const fetchExport = ({ dataset, teamName, modelMode, modelName }) =>
  request('/export', {
    params: { dataset, team_name: teamName, model_mode: modelMode, model_name: modelName },
  })
