import clsx from 'clsx'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { LuShieldAlert, LuShieldCheck } from 'react-icons/lu'
import { Card, CardHeader } from '../ui/Card'

const UNKNOWN_TYPE = 'unknown'
// Типы нарушений c08 из эталонного чек-листа: показываем их даже с нулём, чтобы был виден «чистый» результат
const KNOWN_TYPES = ['insult', 'bypass_offer', 'confidential_leak']

function countByType(dialogs) {
  const counts = new Map(KNOWN_TYPES.map((type) => [type, 0]))
  dialogs
    .filter((row) => row.gross_error)
    .forEach((row) => {
      const types = row.gross_types.length ? row.gross_types : [UNKNOWN_TYPE]
      types.forEach((type) => counts.set(type, (counts.get(type) ?? 0) + 1))
    })
  return [...counts].map(([type, count]) => ({ type, count }))
}

// Risk-монитор по c08: сколько диалогов с каждым типом грубого нарушения, клик — фильтр таблицы
export default function RiskMonitor({ dialogs, filter, onFilter }) {
  const { t } = useTranslation()
  const rows = useMemo(() => countByType(dialogs), [dialogs])
  const label = (type) => (type === UNKNOWN_TYPE ? t('detail.grossUnknownType') : t(`gross.${type}`, { defaultValue: type }))

  return (
    <Card className="flex h-full flex-col pb-3">
      <CardHeader title={t('overview.riskTitle')} hint={t('overview.riskHint')} />
      <ul className="flex flex-1 flex-col justify-center gap-1 px-3">
        {rows.map(({ type, count }) => {
          const active = filter?.type === 'grossType' && filter.value === type
          const Icon = count ? LuShieldAlert : LuShieldCheck
          return (
            <li key={type}>
              <button
                type="button"
                disabled={!count}
                aria-pressed={active}
                onClick={() => onFilter({ type: 'grossType', value: type, label: label(type) })}
                className={clsx(
                  'flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm',
                  count ? 'cursor-pointer hover:bg-surface-muted' : 'text-ink-muted',
                  active && 'ring-2 ring-brand',
                )}
              >
                <Icon className={clsx('size-4 shrink-0', count ? 'text-danger-text' : 'text-brand-text')} />
                <span className="min-w-0 flex-1 truncate">{label(type)}</span>
                <b className={clsx('tabular-nums', count && 'text-danger-text')}>{count}</b>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
