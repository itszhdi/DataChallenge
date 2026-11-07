import clsx from 'clsx'

const CONTROL = 'rounded-lg border border-line bg-canvas px-3 text-sm text-ink placeholder:text-ink-muted'

export function Field({ label, hint, error, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-danger-text">{error}</span>
      ) : (
        hint && <span className="mt-1 block text-xs text-ink-muted">{hint}</span>
      )}
    </label>
  )
}

export function Checkbox({ label, hint, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-start gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-0.5 size-4 accent-brand" />
      <span>
        {label}
        {hint && <span className="mt-0.5 block text-xs text-ink-muted">{hint}</span>}
      </span>
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
