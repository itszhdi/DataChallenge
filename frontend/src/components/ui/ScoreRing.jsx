import { useFormat } from '../../hooks/useFormat'
import { scoreTone } from '../../lib/format'

const RADIUS = 52
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const TONE_STROKE = {
  success: 'stroke-brand',
  warning: 'stroke-warn',
  danger: 'stroke-danger',
  neutral: 'stroke-line',
}

export default function ScoreRing({ value, label }) {
  const format = useFormat()
  return (
    <div className="relative size-32 shrink-0">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r={RADIUS} fill="none" strokeWidth="10" className="stroke-surface-muted" />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - (value ?? 0) / 100)}
          className={TONE_STROKE[scoreTone(value)]}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tabular-nums">{format.number(value)}</span>
        <span className="text-xs text-ink-muted">{label}</span>
      </div>
    </div>
  )
}
