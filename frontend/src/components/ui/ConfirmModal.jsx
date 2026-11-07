import { useTranslation } from 'react-i18next'
import Button from './Button'
import Modal from './Modal'

export default function ConfirmModal({ open, onClose, onConfirm, title, description, confirmLabel }) {
  const { t } = useTranslation()
  return (
    <Modal open={open} onClose={onClose} title={title} description={description}>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>{t('common.cancel')}</Button>
        <Button
          variant="primary"
          onClick={() => {
            onConfirm()
            onClose()
          }}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}
