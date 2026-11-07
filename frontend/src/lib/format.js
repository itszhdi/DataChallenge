import { SCORE_GOOD_FROM, SCORE_WARN_FROM } from './constants'

export const scoreTone = (value) => {
  if (value === null || value === undefined) return 'neutral'
  if (value >= SCORE_GOOD_FROM) return 'success'
  return value >= SCORE_WARN_FROM ? 'warning' : 'danger'
}

export const formatClock = (seconds) => {
  if (seconds === null || seconds === undefined) return '—'
  const whole = Math.max(0, Math.floor(seconds))
  const minutes = String(Math.floor(whole / 60)).padStart(2, '0')
  return `${minutes}:${String(whole % 60).padStart(2, '0')}`
}

// Внутренний id диалога «НАБОР:исходный_id»: пользователю показываем исходный
export const displayId = (id) => (typeof id === 'string' && id.includes(':') ? id.slice(id.indexOf(':') + 1) : id)
