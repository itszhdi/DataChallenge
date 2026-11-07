import clsx from 'clsx'

const TONES = { success: 'bg-brand', warning: 'bg-warn', danger: 'bg-danger', neutral: 'bg-ink-muted' }

export default function ProgressBar({ value, tone = 'success', label }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-1.5 overflow-hidden rounded-full bg-surface-muted"
    >
      <div className={clsx('h-full rounded-full transition-all', TONES[tone])} style={{ width: `${value}%` }} />
    </div>
  )
}
