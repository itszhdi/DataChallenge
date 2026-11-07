import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { fetchExport } from '../../api/exportResults'
import { useApiError } from '../../hooks/useApiError'
import { useDataset } from '../../hooks/useDataset'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { STORAGE_KEYS } from '../../lib/constants'
import { downloadJson } from '../../lib/download'
import Button from '../ui/Button'
import { Field, Input, Select } from '../ui/Field'
import Modal from '../ui/Modal'

const EMPTY_META = { teamName: '', modelMode: '', modelName: '' }

export default function ExportModal({ open, onClose }) {
  const { t } = useTranslation()
  const { dataset } = useDataset()
  const { notify } = useApiError()
  const [meta, setMeta] = useLocalStorage(STORAGE_KEYS.exportMeta, EMPTY_META)
  const change = (field) => (event) => setMeta({ ...meta, [field]: event.target.value })

  const exportResults = useMutation({
    mutationFn: () => fetchExport({ dataset, ...meta, teamName: meta.teamName.trim() }),
    onSuccess: (data) => {
      if (!data.results.length) {
        toast.error(t('export.empty'))
        return
      }
      downloadJson(`cqa-results-${dataset || 'all'}.json`, data)
      toast.success(t('export.done', { count: data.results.length }))
      onClose()
    },
    onError: notify,
  })

  return (
    <Modal open={open} onClose={onClose} title={t('export.title')} description={t('export.description')}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          exportResults.mutate()
        }}
      >
        <Field label={t('export.team')}>
          <Input value={meta.teamName} onChange={change('teamName')} required />
        </Field>
        <Field label={t('export.mode')}>
          <Select value={meta.modelMode} onChange={change('modelMode')}>
            <option value="">{t('export.modeAuto')}</option>
            <option value="remote">remote</option>
            <option value="local">local</option>
          </Select>
        </Field>
        <Field label={t('export.model')} hint={t('export.modelHint')}>
          <Input value={meta.modelName} onChange={change('modelName')} />
        </Field>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" loading={exportResults.isPending}>
            {t('export.submit')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
