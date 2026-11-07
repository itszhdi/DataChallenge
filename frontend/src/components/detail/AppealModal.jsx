import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { useCreateAppeal } from '../../hooks/useAppeals'
import Button from '../ui/Button'
import { Field, Textarea } from '../ui/Field'
import Modal from '../ui/Modal'

export default function AppealModal({ evaluationId, criterion, onClose }) {
  const { t } = useTranslation()
  const [comment, setComment] = useState('')
  const create = useCreateAppeal(() => {
    toast.success(t('appeal.created'))
    onClose()
  })
  return (
    <Modal open onClose={onClose} title={t('appeal.title')} description={criterion.title}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({ evaluationId, criterionId: criterion.id, comment: comment.trim() })
        }}
      >
        <Field label={t('appeal.comment')}>
          <Textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder={t('appeal.commentHint')} required autoFocus />
        </Field>
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>{t('common.cancel')}</Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            {t('appeal.submit')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
