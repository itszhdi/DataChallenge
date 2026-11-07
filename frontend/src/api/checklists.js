import { request } from './client'

export const fetchActiveChecklist = () => request('/checklists/active')

export const fetchChecklist = (id) => request(`/checklists/${id}`)
