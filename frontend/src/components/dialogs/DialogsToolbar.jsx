import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuDownload, LuListChecks, LuPlay, LuRefreshCw, LuUpload } from 'react-icons/lu'
import { useDataset } from '../../hooks/useDataset'
import Button from '../ui/Button'
import ConfirmModal from '../ui/ConfirmModal'
import ExportModal from './ExportModal'
import ImportModal from './ImportModal'

export default function DialogsToolbar({ hasDialogs, isRunning, startBatch, trackJob }) {
  const { t } = useTranslation()
  const { dataset } = useDataset()
  const [modal, setModal] = useState(null)
  const closeModal = () => setModal(null)
  const run = (mode, onlyMissing) => startBatch({ dataset, mode, onlyMissing })
  const disabled = !hasDialogs || isRunning
  return (
    <div className="grid gap-2 sm:flex sm:flex-wrap sm:items-center">
      <Button icon={LuUpload} onClick={() => setModal('import')}>
        {t('dialogs.import')}
      </Button>
      <Button variant="primary" icon={LuPlay} disabled={disabled} onClick={() => run('evaluate', true)}>
        {t('dialogs.evaluateMissing')}
      </Button>
      <Button icon={LuRefreshCw} disabled={disabled} onClick={() => setModal('confirm')}>
        {t('dialogs.evaluateAll')}
      </Button>
      <Button icon={LuListChecks} disabled={disabled} title={t('dialogs.applyChecklistHint')} onClick={() => run('reapply', false)}>
        {t('dialogs.applyChecklist')}
      </Button>
      <Button icon={LuDownload} disabled={!hasDialogs} onClick={() => setModal('export')}>
        {t('export.open')}
      </Button>
      <ImportModal open={modal === 'import'} onClose={closeModal} onJobStarted={trackJob} />
      <ExportModal open={modal === 'export'} onClose={closeModal} />
      <ConfirmModal
        open={modal === 'confirm'}
        onClose={closeModal}
        onConfirm={() => run('evaluate', false)}
        title={t('dialogs.evaluateAll')}
        description={t('dialogs.evaluateAllConfirm')}
        confirmLabel={t('dialogs.evaluateAll')}
      />
    </div>
  )
}
