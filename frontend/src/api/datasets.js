import { request } from './client'

export const fetchDatasets = () => request('/datasets')

export const importDataset = ({ groupId, url }) =>
  request('/datasets/import', { method: 'POST', json: { group_id: groupId || null, url: url || null } })

export const uploadDataset = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request('/datasets/upload', { method: 'POST', formData })
}
