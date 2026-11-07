import clsx from 'clsx'
import { LuLoaderCircle } from 'react-icons/lu'

const VARIANTS = {
  primary: 'bg-brand text-on-brand hover:bg-brand-hover',
  secondary: 'border border-line bg-surface text-ink hover:bg-surface-muted',
  ghost: 'text-ink-muted hover:bg-surface-muted hover:text-ink',
  danger: 'bg-danger text-white hover:opacity-90',
}

const SIZES = { sm: 'h-8 gap-1.5 px-2.5 text-xs', md: 'h-10 gap-2 px-4 text-sm', icon: 'size-10 justify-center' }

export default function Button({ variant = 'secondary', size = 'md', icon: Icon, loading, className, children, ...props }) {
  return (
    <button
      type="button"
      className={clsx(
        'inline-flex shrink-0 items-center justify-center rounded-lg font-medium whitespace-nowrap transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <LuLoaderCircle className="size-4 animate-spin" /> : Icon && <Icon className="size-4" />}
      {children}
    </button>
  )
}
