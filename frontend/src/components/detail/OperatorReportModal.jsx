import { useTranslation } from 'react-i18next'
import { LuDownload } from 'react-icons/lu'
import { toast } from 'sonner'
import { useLabels } from '../../hooks/useLabels'
import { downloadText } from '../../lib/download'
import { buildOperatorReport } from '../../lib/operatorReport'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

export default function OperatorReportModal({ conversationId, summary, turns, onClose }) {
  const { t } = useTranslation()
  const labels = useLabels()
  const report = buildOperatorReport({ conversationId, summary, turns, criterionTitle: labels.criterion, t })

  const download = () => {
    downloadText(`operator-report-${conversationId}.txt`, report)
    toast.success(t('report.done'))
    onClose()
  }

  return (
    <Modal open onClose={onClose} title={t('report.title')} description={t('report.description')}>
      <pre className="mb-4 max-h-80 overflow-y-auto rounded-xl bg-surface-muted p-3 font-sans text-xs leading-relaxed break-words whitespace-pre-wrap">
        {report}
      </pre>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>{t('common.cancel')}</Button>
        <Button variant="primary" icon={LuDownload} onClick={download}>
          {t('report.submit')}
        </Button>
      </div>
    </Modal>
  )
}
