// Цвета графиков берутся из CSS-переменных, поэтому recharts сам следует за темой
export const TONE_FILL = {
  success: 'var(--brand)',
  warning: 'var(--warn)',
  danger: 'var(--danger)',
  neutral: 'var(--ink-muted)',
  info: 'var(--info)',
}

export const AXIS_TICK = { fill: 'var(--ink-muted)', fontSize: 12 }

export const TOOLTIP_PROPS = {
  cursor: { fill: 'var(--surface-muted)' },
  contentStyle: { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, color: 'var(--ink)', fontSize: 13 },
  labelStyle: { color: 'var(--ink)', fontWeight: 600 },
  itemStyle: { color: 'var(--ink)' },
}

export const DIMMED_OPACITY = 0.3

export const barOpacity = (isActive, hasSelection) => (hasSelection && !isActive ? DIMMED_OPACITY : 1)
