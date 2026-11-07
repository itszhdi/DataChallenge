import clsx from 'clsx'

export function Card({ glass, className, ...props }) {
  return <div className={clsx('rounded-2xl border border-line', glass ? 'glass' : 'bg-surface', className)} {...props} />
}

export function CardHeader({ title, hint, actions }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 p-5 pb-3">
      <div>
        <h2 className="text-base font-semibold">{title}</h2>
        {hint && <p className="mt-0.5 text-xs text-ink-muted">{hint}</p>}
      </div>
      {actions}
    </div>
  )
}
