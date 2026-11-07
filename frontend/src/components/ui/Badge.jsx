import clsx from 'clsx'

const TONES = {
  neutral: 'bg-surface-muted text-ink-muted',
  success: 'bg-brand-soft text-brand-text',
  warning: 'bg-warn-soft text-warn-text',
  danger: 'bg-danger-soft text-danger-text',
  info: 'bg-info-soft text-info-text',
}

export default function Badge({ tone = 'neutral', icon: Icon, className, children, ...props }) {
  return (
    <span
      className={clsx('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', TONES[tone], className)}
      {...props}
    >
      {Icon && <Icon className="size-3.5" />}
      {children}
    </span>
  )
}
