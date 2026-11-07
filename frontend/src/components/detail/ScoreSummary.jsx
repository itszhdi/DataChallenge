import { useTranslation } from 'react-i18next'
import { LuCircleCheck, LuTriangleAlert } from 'react-icons/lu'
import clsx from 'clsx'
import { useFormat } from '../../hooks/useFormat'
import { useLabels } from '../../hooks/useLabels'
import { scoreTone } from '../../lib/format'
import Badge from '../ui/Badge'
import { Card } from '../ui/Card'
import ProgressBar from '../ui/ProgressBar'
import ScoreRing from '../ui/ScoreRing'

function GrossErrors({ gross }) {
  const { t } = useTranslation()
  const types = gross.types.map((type) => t(`gross.${type}`, { defaultValue: type })).join(', ')
  return (
    <div
      className={clsx(
        'mt-4 flex items-start gap-2 rounded-xl p-3 text-sm',
        gross.detected ? 'bg-danger-soft text-danger-text' : 'bg-brand-soft text-brand-text',
      )}
    >
      {gross.detected ? <LuTriangleAlert className="mt-0.5 size-4 shrink-0" /> : <LuCircleCheck className="mt-0.5 size-4 shrink-0" />}
      {gross.detected ? t('detail.grossDetected', { types: types || t('detail.grossUnknownType') }) : t('detail.grossNone')}
    </div>
  )
}

export default function ScoreSummary({ card }) {
  const { t } = useTranslation()
  const format = useFormat()
  const labels = useLabels()
  const { final, original, meta, checklist } = card
  const sections = final.sections.filter((section) => section.max > 0)
  return (
    <Card className="p-5">
      <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
        <ScoreRing value={final.total} label={t('detail.outOf100')} />
        <div className="w-full min-w-0 flex-1">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-base font-semibold">{t('detail.total')}</h2>
            {final.preliminary && <Badge tone="warning">{t('status.preliminary')}</Badge>}
          </div>
          <div className="space-y-2.5">
            {sections.map((section) => (
              <div key={section.id}>
                <div className="mb-1 flex justify-between gap-3 text-xs">
                  <span className="text-ink-muted">{labels.section(section.id, section.title)}</span>
                  <span className="tabular-nums">
                    {format.number(section.points)} / {format.number(section.max)}
                  </span>
                </div>
                <ProgressBar
                  label={section.title}
                  value={(section.points / section.max) * 100}
                  tone={scoreTone((section.points / section.max) * 100)}
                />
              </div>
            ))}
          </div>
          {original.total !== final.total && (
            <p className="mt-3 text-sm">
              {t('detail.totalChanged', { original: format.number(original.total), final: format.number(final.total) })}
            </p>
          )}
          <p className="mt-2 text-xs text-ink-muted">
            {t('detail.checklistVersion', { version: checklist.version })}
            {!checklist.is_active && ` (${t('detail.checklistInactive')})`}
            {meta.model && ` · ${meta.model}`}
            {meta.seconds && ` · ${t('detail.seconds', { value: format.number(meta.seconds) })}`}
          </p>
        </div>
      </div>
      <GrossErrors gross={final.gross_errors} />
      {final.warnings.length > 0 && (
        <details className="mt-3 text-xs text-ink-muted">
          <summary className="cursor-pointer">
            {t('detail.warnings')} ({final.warnings.length})
          </summary>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {final.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  )
}
