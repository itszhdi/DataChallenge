import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuFileJson } from 'react-icons/lu'
import { useAppSettings } from '../../hooks/useAppSettings'
import { useImportDataset } from '../../hooks/useImportDataset'
import Button from '../ui/Button'
import { Field, Input } from '../ui/Field'
import Modal from '../ui/Modal'

export default function ImportModal({ open, onClose, onJobStarted }) {
  const { t } = useTranslation()
  const { data: settings } = useAppSettings()
  const [editedGroupId, setGroupId] = useState(null)
  const groupId = editedGroupId ?? settings?.default_group_id ?? ''
  const [url, setUrl] = useState('')
  const { mutate, isPending } = useImportDataset((result) => {
    if (result.job_id) onJobStarted(result.job_id)
    onClose()
  })

  const submitFile = (event) => {
    const file = event.target.files[0]
    event.target.value = ''
    if (file) mutate({ file })
  }

  return (
    <Modal open={open} onClose={onClose} title={t('import.title')} description={t('import.description')}>
      <div className="space-y-5">
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault()
            mutate({ groupId: groupId.trim() })
          }}
        >
          <Field label={t('import.groupId')} hint={t('import.groupIdHint')}>
            <Input value={groupId} onChange={(event) => setGroupId(event.target.value)} required />
          </Field>
          <Button type="submit" variant="primary" loading={isPending}>
            {t('import.fromApi')}
          </Button>
        </form>
        <form
          className="space-y-2 border-t border-line pt-4"
          onSubmit={(event) => {
            event.preventDefault()
            mutate({ url: url.trim(), groupId: groupId.trim() })
          }}
        >
          <Field label={t('import.url')} hint={t('import.urlHint')}>
            <Input type="url" pattern="https://.*" value={url} onChange={(event) => setUrl(event.target.value)} required />
          </Field>
          <Button type="submit" loading={isPending}>
            {t('import.fromUrl')}
          </Button>
        </form>
        <div className="border-t border-line pt-4">
          <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-line px-4 text-sm font-medium hover:bg-surface-muted">
            <LuFileJson className="size-4" />
            {t('import.fromFile')}
            <input type="file" accept=".json,application/json" className="sr-only" onChange={submitFile} />
          </label>
        </div>
      </div>
    </Modal>
  )
}
