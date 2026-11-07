import { request } from './client'

export const fetchActiveChecklist = () => request('/checklists/active')

export const fetchChecklist = (id) => request(`/checklists/${id}`)

export const fetchDefaultChecklist = () => request('/checklists/default')

export const saveChecklist = ({ data, comment }) => request('/checklists', { method: 'POST', json: { data, comment } })
