import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuCircleAlert, LuCircleCheck, LuDownload, LuHardDriveDownload } from 'react-icons/lu'
import { toast } from 'sonner'
import { previewSubmission, saveSubmission, submissionDownloadUrl } from '../../api/export'
import { useApiError } from '../../hooks/useApiError'
import { useDataset } from '../../hooks/useDataset'
import Button from '../ui/Button'
import { Field, Select } from '../ui/Field'
import Modal from '../ui/Modal'

const TARGETS = ['dev', 'prod']
const WARNINGS_SHOWN = 5

// Как на бэкенде: DEV → results/dev, контрольный набор организаторов → results/prod
const defaultTarget = (dataset) => (dataset.trim().toUpperCase() === 'DEV' ? 'dev' : 'prod')

function Check({ check, submission }) {
  const { t } = useTranslation()
  const { errors, warnings, counts } = check
  const hidden = warnings.length - WARNINGS_SHOWN
  return (
    <div role="status" className="space-y-2 rounded-xl bg-surface-muted p-3 text-sm">
      <p className="flex items-center gap-2 font-medium">
        {errors.length ? <LuCircleAlert className="size-4 text-danger-text" /> : <LuCircleCheck className="size-4 text-brand-text" />}
        {t('export.counts', { ok: counts.ok, error: counts.error })}
      </p>
      <p className="text-xs text-ink-muted">
        {t('export.teamLine', { team: submission.team_name })} · {t('export.modelLine', { name: submission.model.name, mode: submission.model.mode })}
      </p>
      {errors.length > 0 && (
        <ul className="space-y-1 text-xs text-danger-text">
          {errors.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {warnings.length > 0 && (
        <ul className="space-y-1 text-xs text-warn-text">
          {warnings.slice(0, WARNINGS_SHOWN).map((line) => (
            <li key={line}>{line}</li>
          ))}
          {hidden > 0 && <li>{t('export.moreWarnings', { count: hidden })}</li>}
        </ul>
      )}
    </div>
  )
}

// Выгрузка строго в формате организаторов: results/<dev|prod>/results.json, перед записью — проверка файла
export default function ExportModal({ open, onClose }) {
  const { t } = useTranslation()
  const { dataset: current, datasets } = useDataset()
  const { notify } = useApiError()
  const [picked, setPicked] = useState('')
  const [targetOverride, setTargetOverride] = useState(null)
  // Смешивать наборы в одном файле нельзя: при «все наборы» берём первый, пока не выбрали другой
  const dataset = picked || current || datasets[0]?.dataset || ''
  const target = targetOverride ?? defaultTarget(dataset)
  // Название команды подставляет бэкенд (TEAM_NAME, по умолчанию Cyberpsychosis)
  const options = { dataset, target }
  const isReady = Boolean(dataset)

  const preview = useQuery({
    queryKey: ['submission', options],
    queryFn: () => previewSubmission(options),
    enabled: open && Boolean(dataset),
    placeholderData: keepPreviousData,
  })
  const check = preview.data?.check
  const hasErrors = Boolean(check?.errors.length)

  const save = useMutation({
    mutationFn: saveSubmission,
    onSuccess: (saved) => {
      toast.success(t('export.saved', { file: `results/${saved.target}/results.json` }), {
        description: t('export.counts', { ok: saved.counts.ok, error: saved.counts.error }),
      })
      preview.refetch()
    },
    // 422 приходит объектом с message и списком ошибок проверки
    onError: (error) => (error.detail?.message ? toast.error(error.detail.message) : notify(error)),
  })

  const chooseDataset = (value) => {
    setPicked(value)
    setTargetOverride(null)
  }

  return (
    <Modal open={open} onClose={onClose} title={t('export.title')} description={t('export.description')}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('export.dataset')}>
            <Select value={dataset} onChange={(event) => chooseDataset(event.target.value)}>
              {datasets.map((item) => (
                <option key={item.dataset} value={item.dataset}>
                  {item.dataset} · {item.total}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('export.target')} hint={t('export.targetHint', { path: `results/${target}/results.json` })}>
            <Select value={target} onChange={(event) => setTargetOverride(event.target.value)}>
              {TARGETS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {preview.isError && <p className="text-sm text-danger-text">{t('export.previewFailed')}</p>}
        {check && <Check check={check} submission={preview.data.submission} />}
        <div className="grid gap-2 sm:flex sm:justify-end">
          <Button icon={LuHardDriveDownload} loading={save.isPending} disabled={!isReady || hasErrors || !check} onClick={() => save.mutate(options)}>
            {t('export.save', { target })}
          </Button>
          <Button
            variant="primary"
            icon={LuDownload}
            disabled={!isReady}
            onClick={() => {
              window.location.href = submissionDownloadUrl(options)
            }}
          >
            {t('export.download')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
