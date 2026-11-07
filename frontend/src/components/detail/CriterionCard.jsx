import { useTranslation } from 'react-i18next'
import { LuFlag } from 'react-icons/lu'
import { useFormat } from '../../hooks/useFormat'
import { useLabels } from '../../hooks/useLabels'
import { answerLabel, answerTone, scaleMaxOf } from '../../lib/answers'
import { formatClock } from '../../lib/format'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import AppealReview from './AppealReview'
import TurnRefText from './TurnRefText'

const MAX_QUOTES = 2

function Points({ item }) {
  const { t } = useTranslation()
  const format = useFormat()
  if (item.type === 'flag') return null
  let result = `${format.number(item.final_points)} / ${format.number(item.effective_weight)}`
  if (item.status === 'error') result = t('detail.excludedFromTotal')
  else if (item.na) result = t('detail.weightRedistributed')
  return (
    <span className="text-xs text-ink-muted">
      {result} · {t('detail.weight', { value: format.number(item.weight) })}
    </span>
  )
}

function ResolvedAppeal({ appeal, item, original, scaleMax }) {
  const { t } = useTranslation()
  const before = answerLabel(original, scaleMax, t)
  const after = answerLabel({ ...item, ...appeal.new_answer }, scaleMax, t)
  return (
    <div className="mt-3 rounded-xl bg-surface-muted p-3 text-sm">
      <p className="text-ink-muted">{t('appeal.history', { id: appeal.id, comment: appeal.comment })}</p>
      <p className="mt-1">
        {appeal.decision === 'changed' ? t('appeal.decisionChanged', { before, after }) : t('appeal.decisionUpheld', { before })}
      </p>
      <p className="mt-1 text-ink-muted">
        {t('appeal.reason')}: {appeal.reason}
      </p>
    </div>
  )
}

export default function CriterionCard({ item, original, criterion, appeals, turns, onTurn, onAppeal }) {
  const { t } = useTranslation()
  const labels = useLabels()
  const scaleMax = scaleMaxOf(criterion)
  const evidence = (item.evidence_ids ?? []).filter((turn) => turns[turn - 1])
  const openAppeal = appeals.find((appeal) => appeal.status === 'open')
  const resolved = appeals.filter((appeal) => appeal.status === 'resolved')
  const title = labels.criterion(item.id, item.title)

  return (
    <article className="border-b border-line p-5 last:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-sm font-semibold">{title}</h3>
        <Badge tone={answerTone(item, scaleMax)}>{answerLabel(item, scaleMax, t)}</Badge>
        <Points item={item} />
        {!openAppeal && (
          <Button size="sm" icon={LuFlag} onClick={() => onAppeal({ id: item.id, title })}>
            {t('appeal.open')}
          </Button>
        )}
      </div>
      {item.explanation && (
        <p className="mt-2 text-sm leading-relaxed">
          <TurnRefText text={item.explanation} turnCount={turns.length} onTurn={onTurn} />
        </p>
      )}
      {item.checked_range && (
        <p className="mt-1.5 text-xs text-ink-muted">
          {t('detail.checkedRange')}: <TurnRefText text={item.checked_range} turnCount={turns.length} onTurn={onTurn} />
        </p>
      )}
      {item.na && criterion?.na_condition && (
        <p className="mt-1.5 text-xs text-ink-muted">
          {t('detail.naCondition')}: {criterion.na_condition}
        </p>
      )}
      {evidence.length > 0 && (
        <div className="mt-2.5 space-y-1.5">
          {evidence.slice(0, MAX_QUOTES).map((turn) => (
            <blockquote key={turn} className="border-l-2 border-warn pl-3 text-xs text-ink-muted">
              {turns[turn - 1].text}
            </blockquote>
          ))}
          <div className="flex flex-wrap gap-1.5">
            {evidence.map((turn) => (
              <button
                key={turn}
                type="button"
                onClick={() => onTurn(turn)}
                className="rounded-md border border-line px-2 py-0.5 text-xs text-brand-text tabular-nums hover:bg-surface-muted"
              >
                #{turn} · {formatClock(turns[turn - 1].offset_sec)}
              </button>
            ))}
          </div>
        </div>
      )}
      {resolved.map((appeal) => (
        <ResolvedAppeal key={appeal.id} appeal={appeal} item={item} original={original} scaleMax={scaleMax} />
      ))}
      {openAppeal && <AppealReview key={openAppeal.id} appeal={openAppeal} currentLabel={answerLabel(item, scaleMax, t)} />}
    </article>
  )
}
