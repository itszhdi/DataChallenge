import clsx from 'clsx'

const CONTROL = 'rounded-lg border border-line bg-canvas px-3 text-sm text-ink placeholder:text-ink-muted'

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-muted">{hint}</span>}
    </label>
  )
}

export function Input({ className, ...props }) {
  return <input className={clsx(CONTROL, 'h-10 w-full', className)} {...props} />
}

export function Textarea({ className, ...props }) {
  return <textarea rows={3} className={clsx(CONTROL, 'w-full py-2', className)} {...props} />
}

export function Select({ className, children, ...props }) {
  return (
    <select className={clsx(CONTROL, 'h-10 pr-8', className ?? 'w-full')} {...props}>
      {children}
    </select>
  )
}
