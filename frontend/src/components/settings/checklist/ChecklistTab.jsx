import * as Accordion from '@radix-ui/react-accordion'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuPlus, LuRotateCcw, LuSave, LuScale, LuTriangleAlert } from 'react-icons/lu'
import { toast } from 'sonner'
import { useChecklistDraft } from '../../../hooks/useChecklistDraft'
import { useDataset } from '../../../hooks/useDataset'
import { useFormat } from '../../../hooks/useFormat'
import { useJob } from '../../../hooks/useJob'
import { validateChecklist, weightTotal } from '../../../lib/checklist'
import Badge from '../../ui/Badge'
import Button from '../../ui/Button'
import { Card } from '../../ui/Card'
import ConfirmModal from '../../ui/ConfirmModal'
import { ErrorState, LoadingState } from '../../ui/States'
import ChecklistDiff from './ChecklistDiff'
import CriterionEditor from './CriterionEditor'

const TARGET_TOTAL = 100

export default function ChecklistTab() {
  const { t } = useTranslation()
  const format = useFormat()
  const { dataset } = useDataset()
  const { isRunning, start } = useJob()
  const [openIds, setOpenIds] = useState([])
  const [errors, setErrors] = useState({})
  const [saved, setSaved] = useState(null)
  const [confirmReset, setConfirmReset] = useState(false)

  const checklist = useChecklistDraft({
    onSaved: (result) => {
      setSaved(result)
      setErrors({})
      toast.success(t('settings.checklist.saved', { version: result.checklist.version }))
    },
    onDefaultLoaded: () => toast.success(t('settings.checklist.defaultLoaded')),
  })
  const { active, draft } = checklist

  if (active.isLoading) return <LoadingState />
  if (active.error) return <ErrorState error={active.error} onRetry={active.refetch} />

  const total = weightTotal(draft.criteria)
  const isBalanced = total === TARGET_TOTAL

  const add = () => {
    const id = checklist.addCriterion(t('settings.checklist.newCriterion'))
    setOpenIds([...openIds, id])
  }

  const save = () => {
    const found = validateChecklist(draft)
    setErrors(found)
    if (Object.keys(found).length) {
      setOpenIds([...new Set([...openIds, ...Object.keys(found)])])
      toast.error(t('settings.validation.failed'))
      return
    }
    checklist.save.mutate()
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="mr-auto min-w-0">
          <h2 className="text-lg font-semibold">{t('settings.checklist.title')}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge tone={isBalanced ? 'success' : 'warning'} icon={isBalanced ? undefined : LuTriangleAlert}>
              {t('settings.checklist.total', { value: format.number(total) })}
            </Badge>
            {!isBalanced && (
              <Button size="sm" icon={LuScale} onClick={checklist.balanceWeights}>
                {t('settings.checklist.autoBalance')}
              </Button>
            )}
            {checklist.isDirty && <span className="text-xs text-warn-text">{t('settings.checklist.unsaved')}</span>}
          </div>
        </div>
        <div className="grid w-full gap-2 sm:flex sm:w-auto sm:flex-wrap">
          <Button icon={LuPlus} onClick={add}>
            {t('settings.checklist.add')}
          </Button>
          <Button icon={LuRotateCcw} onClick={() => setConfirmReset(true)}>
            {t('settings.checklist.reset')}
          </Button>
          <Button variant="primary" icon={LuSave} loading={checklist.save.isPending} disabled={!checklist.isDirty} onClick={save}>
            {t('settings.checklist.save')}
          </Button>
        </div>
      </div>

      {saved && (
        <ChecklistDiff
          diff={saved.diff}
          version={saved.checklist.version}
          isRunning={isRunning}
          onApply={() => {
            start({ dataset, mode: 'reapply' })
            setSaved(null)
          }}
        />
      )}

      <Card>
        <Accordion.Root type="multiple" value={openIds} onValueChange={setOpenIds}>
          {draft.criteria.map((criterion, index) => (
            <CriterionEditor
              key={criterion.id}
              criterion={criterion}
              position={index + 1}
              sections={draft.sections}
              errors={errors[criterion.id]}
              canRemove={draft.criteria.length > 1}
              onChange={(change) => checklist.updateCriterion(criterion.id, change)}
              onRemove={() => checklist.removeCriterion(criterion.id)}
            />
          ))}
        </Accordion.Root>
      </Card>

      <ConfirmModal
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        onConfirm={() => checklist.loadDefault.mutate()}
        title={t('settings.checklist.reset')}
        description={t('settings.checklist.resetConfirm')}
        confirmLabel={t('settings.checklist.reset')}
      />
    </>
  )
}
