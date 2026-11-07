import { useTranslation } from 'react-i18next'
import { LuListChecks } from 'react-icons/lu'
import Badge from '../../ui/Badge'
import Button from '../../ui/Button'
import { Card } from '../../ui/Card'

const GROUPS = [
  { field: 'changed', labelKey: 'settings.diff.changed', tone: 'warning' },
  { field: 'new', labelKey: 'settings.diff.added', tone: 'success' },
  { field: 'weight_only', labelKey: 'settings.diff.weightOnly', tone: 'neutral' },
  { field: 'removed', labelKey: 'settings.diff.removed', tone: 'danger' },
]

export default function ChecklistDiff({ diff, version, isRunning, onApply }) {
  const { t } = useTranslation()
  const groups = GROUPS.filter(({ field }) => diff[field].length > 0)
  return (
    <Card className="mb-4 p-4">
      <p className="text-sm font-semibold">{t('settings.diff.title', { version })}</p>
      {groups.map(({ field, labelKey, tone }) => (
        <div key={field} className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-ink-muted">{t(labelKey)}:</span>
          {diff[field].map((id) => (
            <Badge key={id} tone={tone}>
              {id}
            </Badge>
          ))}
        </div>
      ))}
      <p className="mt-2 text-xs text-ink-muted">
        {diff.needs_llm.length ? t('settings.diff.model', { ids: diff.needs_llm.join(', ') }) : t('settings.diff.noModel')}
      </p>
      <Button variant="primary" icon={LuListChecks} className="mt-3" loading={isRunning} onClick={onApply}>
        {t('settings.diff.apply')}
      </Button>
    </Card>
  )
}
