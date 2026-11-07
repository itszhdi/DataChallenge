export default function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 [&>*]:max-sm:w-full">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
