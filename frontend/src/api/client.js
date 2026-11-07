import { API_URL } from '../lib/constants'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

const readDetail = (body) => {
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => String(item.msg ?? '').replace(/^Value error, /, '')).join('; ')
  }
  return body?.detail
}

export const buildUrl = (path, params = {}) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  ).toString()
  return `${API_URL}${path}${query ? `?${query}` : ''}`
}

export async function request(path, { method = 'GET', params, json, formData } = {}) {
  let response
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers: json === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: formData ?? (json === undefined ? undefined : JSON.stringify(json)),
    })
  } catch {
    throw new ApiError(0)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, readDetail(body))
  return body
}
