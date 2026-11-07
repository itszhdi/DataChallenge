import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { LuDownload, LuHardDriveDownload } from 'react-icons/lu'
import { toast } from 'sonner'
import { exportDownloadUrl, saveExport } from '../../api/export'
import { useApiError } from '../../hooks/useApiError'
import { useAppSettings } from '../../hooks/useAppSettings'
import { useDataset } from '../../hooks/useDataset'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { STORAGE_KEYS } from '../../lib/constants'
import Button from '../ui/Button'
import { Field, Input, Select } from '../ui/Field'
import Modal from '../ui/Modal'

const MODEL_MODES = ['local', 'remote']

export default function ExportModal({ open, onClose }) {
  const { t } = useTranslation()
  const { dataset } = useDataset()
  const { notify } = useApiError()
  const { data: settings } = useAppSettings()
  const [teamName, setTeamName] = useLocalStorage(STORAGE_KEYS.exportTeam, '')
  const [modelMode, setModelMode] = useLocalStorage(STORAGE_KEYS.exportMode, '')
  const [modelName, setModelName] = useLocalStorage(STORAGE_KEYS.exportModel, '')
  const activeModel = settings?.profiles?.[settings.llm_profile]?.model
  const options = { dataset, teamName: teamName.trim(), modelMode, modelName: modelName.trim() }
  const isReady = Boolean(options.teamName)

  const save = useMutation({
    mutationFn: saveExport,
    onSuccess: (saved) => {
      const counts = Object.entries(saved.counts ?? {})
        .map(([status, count]) => `${status} ${count}`)
        .join(' · ')
      toast.success(t('export.saved', { file: saved.file }), { description: counts })
    },
    onError: notify,
  })

  return (
    <Modal open={open} onClose={onClose} title={t('export.title')} description={t('export.description', { dataset: dataset || t('export.allDatasets') })}>
      <div className="space-y-4">
        <Field label={t('export.team')} error={isReady ? null : t('export.teamRequired')}>
          <Input value={teamName} maxLength={200} onChange={(event) => setTeamName(event.target.value)} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('export.mode')}>
            <Select value={modelMode} onChange={(event) => setModelMode(event.target.value)}>
              <option value="">{t('export.modeAuto')}</option>
              {MODEL_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {t(`export.mode_${mode}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('export.model')} hint={t('export.modelHint')}>
            <Input value={modelName} maxLength={200} placeholder={activeModel} onChange={(event) => setModelName(event.target.value)} />
          </Field>
        </div>
        <p className="text-xs text-ink-muted">{t('export.hint')}</p>
        <div className="grid gap-2 sm:flex sm:justify-end">
          <Button icon={LuHardDriveDownload} loading={save.isPending} disabled={!isReady} onClick={() => save.mutate(options)}>
            {t('export.save')}
          </Button>
          <Button
            variant="primary"
            icon={LuDownload}
            disabled={!isReady}
            onClick={() => {
              window.location.href = exportDownloadUrl(options)
            }}
          >
            {t('export.download')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
