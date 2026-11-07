import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuChevronRight, LuGauge, LuScale, LuShieldAlert, LuTarget } from 'react-icons/lu'
import { useFormat } from '../../hooks/useFormat'
import { useLabels } from '../../hooks/useLabels'
import { scoreTone } from '../../lib/format'
import ProgressBar from '../ui/ProgressBar'

const VALUE_TONE = { success: 'text-brand-text', warning: 'text-warn-text', danger: 'text-danger-text', neutral: 'text-ink' }

function Kpi({ icon: Icon, label, value, tone = 'neutral', critical, active, onClick, children }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      aria-pressed={onClick ? active : undefined}
      onClick={onClick}
      className={clsx(
        'flex min-w-0 flex-col rounded-2xl border bg-surface p-5 text-left',
        critical ? 'border-danger bg-danger-soft' : 'border-line',
        onClick && 'cursor-pointer transition-colors hover:border-brand',
        active && 'ring-2 ring-brand',
      )}
    >
      <span className="flex items-center gap-2 text-sm text-ink-muted">
        <Icon className="size-4 shrink-0" />
        {label}
        {onClick && <LuChevronRight className="ml-auto size-4 shrink-0" />}
      </span>
      <span className={clsx('mt-3 text-2xl font-bold tracking-tight', VALUE_TONE[tone])}>{value}</span>
      <span className="mt-1.5 text-xs text-ink-muted">{children}</span>
    </Tag>
  )
}

export default function KpiCards({ data, filter, onFilter }) {
  const { t } = useTranslation()
  const format = useFormat()
  const labels = useLabels()
  const { summary, bottleneck, appeals } = data
  const isActive = (type, value) => filter?.type === type && filter?.value === value
  const score = summary.average_score
  const fatalLabel = t('overview.fatal')
  const bottleneckTitle = bottleneck && labels.criterion(bottleneck.criterion_id, bottleneck.title)

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Kpi icon={LuGauge} label={t('overview.quality')} value={format.percent(score)} tone={scoreTone(score)}>
        <span className="mb-1.5 block">{t('overview.target', { value: format.number(summary.target_score) })}</span>
        <ProgressBar label={t('overview.quality')} value={score ?? 0} tone={scoreTone(score)} />
      </Kpi>
      <Kpi
        icon={LuShieldAlert}
        label={fatalLabel}
        value={t('overview.fatalValue', { count: summary.fatal_count, percent: format.percent(summary.fatal_percent) })}
        tone={summary.fatal_count ? 'danger' : 'success'}
        critical={summary.fatal_count > 0}
        active={isActive('gross', true)}
        onClick={summary.fatal_count ? () => onFilter({ type: 'gross', value: true, label: fatalLabel }) : undefined}
      >
        {t('overview.fatalHint')}
      </Kpi>
      <Kpi
        icon={LuTarget}
        label={t('overview.bottleneck')}
        value={bottleneck ? format.percent(bottleneck.avg_percent) : '—'}
        tone={scoreTone(bottleneck?.avg_percent)}
        active={bottleneck && isActive('criterion', bottleneck.criterion_id)}
        onClick={bottleneck ? () => onFilter({ type: 'criterion', value: bottleneck.criterion_id, label: bottleneckTitle }) : undefined}
      >
        {bottleneckTitle ?? t('common.noData')}
      </Kpi>
      <Kpi
        icon={LuScale}
        label={t('overview.appeals')}
        value={t('overview.appealsValue', { filed: appeals.filed, changed: appeals.changed })}
      >
        {appeals.changed_percent === null
          ? t('overview.appealsNoDecisions')
          : t('overview.appealsHint', { percent: format.percent(appeals.changed_percent), open: appeals.open })}
      </Kpi>
    </div>
  )
}
