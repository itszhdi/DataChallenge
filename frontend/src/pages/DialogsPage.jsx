import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import DialogsTable from '../components/dialogs/DialogsTable'
import DialogsToolbar from '../components/dialogs/DialogsToolbar'
import JobProgress from '../components/dialogs/JobProgress'
import DatasetSelect from '../components/layout/DatasetSelect'
import PageHeader from '../components/layout/PageHeader'
import { Card } from '../components/ui/Card'
import { Select } from '../components/ui/Field'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { useBatchJob } from '../hooks/useBatchJob'
import { useConversations, useEvaluateConversation } from '../hooks/useConversations'
import { useDataset } from '../hooks/useDataset'
import { useFormat } from '../hooks/useFormat'
import { CHANNEL_LABEL_KEYS, CHANNELS } from '../lib/constants'

const ALL = 'all'

export default function DialogsPage() {
  const { t } = useTranslation()
  const format = useFormat()
  const { dataset } = useDataset()
  const conversations = useConversations(dataset)
  const { job, isRunning, start, dismiss } = useBatchJob()
  const [channel, setChannel] = useState(ALL)
  const [appeals, setAppeals] = useState(ALL)

  const evaluate = useEvaluateConversation({
    onEvaluated: (card) => toast.success(t('dialogs.evaluated', { total: format.number(card.final.total) })),
  })
  const { mutate: evaluateDialog } = evaluate

  const rows = useMemo(
    () =>
      (conversations.data ?? []).filter(
        (row) => (channel === ALL || row.channel === channel) && (appeals === ALL || row.open_appeals > 0),
      ),
    [conversations.data, channel, appeals],
  )
  const failures = useMemo(() => new Map((job?.failed ?? []).map((item) => [item.conversation_id, item.reason])), [job])
  const onEvaluate = useCallback((id) => evaluateDialog(id), [evaluateDialog])

  const renderContent = () => {
    if (conversations.isLoading) return <LoadingState />
    if (conversations.error) return <ErrorState error={conversations.error} onRetry={conversations.refetch} />
    if (!conversations.data.length) return <EmptyState title={t('common.noData')} description={t('dialogs.empty')} />
    if (!rows.length) return <EmptyState title={t('dialogs.nothingFound')} />
    return (
      <DialogsTable
        rows={rows}
        evaluatingId={evaluate.isPending ? evaluate.variables : null}
        failures={failures}
        isBusy={isRunning || evaluate.isPending}
        onEvaluate={onEvaluate}
      />
    )
  }

  return (
    <>
      <PageHeader
        title={t('nav.dialogs')}
        actions={<DialogsToolbar hasDialogs={Boolean(conversations.data?.length)} isRunning={isRunning} startBatch={start} />}
      />
      {job && <JobProgress job={job} onDismiss={dismiss} />}
      <Card glass>
        <div className="flex flex-wrap items-center gap-2 p-4">
          <DatasetSelect />
          <Select aria-label={t('table.format')} value={channel} onChange={(event) => setChannel(event.target.value)} className="w-full sm:w-auto">
            <option value={ALL}>{t('dialogs.allFormats')}</option>
            {CHANNELS.map((value) => (
              <option key={value} value={value}>
                {t(CHANNEL_LABEL_KEYS[value])}
              </option>
            ))}
          </Select>
          <Select aria-label={t('table.appeals')} value={appeals} onChange={(event) => setAppeals(event.target.value)} className="w-full sm:w-auto">
            <option value={ALL}>{t('dialogs.allAppeals')}</option>
            <option value="open">{t('dialogs.openAppeals')}</option>
          </Select>
          <span className="ml-auto text-sm text-ink-muted">{t('dialogs.count', { count: rows.length })}</span>
        </div>
        {renderContent()}
      </Card>
    </>
  )
}
