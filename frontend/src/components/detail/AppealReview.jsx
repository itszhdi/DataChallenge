import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuGavel } from 'react-icons/lu'
import { toast } from 'sonner'
import { useResolveAppeal } from '../../hooks/useAppeals'
import { useFormat } from '../../hooks/useFormat'
import Button from '../ui/Button'
import { Field, Select, Textarea } from '../ui/Field'
import TurnMessage from './TurnMessage'

const NA_OPTION = 'na'

function decisionOptions(criterion, t) {
  const options =
    criterion.type === 'scale'
      ? [...criterion.scale].sort((a, b) => b.value - a.value).map((step) => ({ value: String(step.value), label: `${step.value} — ${step.description}` }))
      : [
          { value: '1', label: t(criterion.type === 'flag' ? 'answer.detected' : 'answer.yes') },
          { value: '0', label: t(criterion.type === 'flag' ? 'answer.notDetected' : 'answer.no') },
        ]
  return criterion.na_allowed ? [...options, { value: NA_OPTION, label: t('answer.na') }] : options
}

// Блок проверяющего: спорная оценка, комментарий, фрагмент диалога и решение
export default function AppealReview({ appeal, currentLabel }) {
  const { t } = useTranslation()
  const format = useFormat()
  const options = decisionOptions(appeal.criterion, t)
  const [answer, setAnswer] = useState(options[0].value)
  const [reason, setReason] = useState('')
  const evidence = new Set(appeal.disputed.evidence_ids ?? [])
  const resolve = useResolveAppeal((result) =>
    toast.success(t('appeal.resolved', { original: format.number(result.original_total), final: format.number(result.final_total) })),
  )

  const submit = (decision) => {
    if (!reason.trim()) {
      toast.error(t('appeal.reasonRequired'))
      return
    }
    const changes = answer === NA_OPTION ? { na: true } : { value: Number(answer) }
    resolve.mutate({ appealId: appeal.id, decision, reason: reason.trim(), ...(decision === 'changed' ? changes : {}) })
  }

  return (
    <section className="mt-3 rounded-xl border border-warn/50 bg-warn-soft/40 p-3">
      <h4 className="flex items-center gap-2 text-sm font-semibold">
        <LuGavel className="size-4" />
        {t('appeal.reviewTitle', { id: appeal.id })}
      </h4>
      <dl className="mt-2 space-y-1 text-sm">
        <div>
          <dt className="inline text-ink-muted">{t('appeal.disputed')}: </dt>
          <dd className="inline font-medium">{currentLabel}</dd>
        </div>
        <div>
          <dt className="inline text-ink-muted">{t('appeal.comment')}: </dt>
          <dd className="inline">{appeal.comment}</dd>
        </div>
      </dl>
      <p className="mt-3 mb-1 text-xs font-medium text-ink-muted">{t('appeal.fragment')}</p>
      <div className="space-y-1.5">
        {appeal.fragment.map((turn) => (
          <TurnMessage key={turn.index} turn={turn} highlighted={evidence.has(turn.index)} />
        ))}
      </div>
      <div className="mt-3 space-y-3">
        <Field label={t('appeal.newAnswer')} hint={t('appeal.newAnswerHint')}>
          <Select value={answer} onChange={(event) => setAnswer(event.target.value)}>
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('appeal.reason')}>
          <Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder={t('appeal.reasonHint')} />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button loading={resolve.isPending} onClick={() => submit('upheld')}>
            {t('appeal.uphold')}
          </Button>
          <Button variant="primary" loading={resolve.isPending} onClick={() => submit('changed')}>
            {t('appeal.change')}
          </Button>
        </div>
      </div>
    </section>
  )
}
