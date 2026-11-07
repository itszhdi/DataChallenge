import { useCallback, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuArrowLeft, LuDownload, LuListChecks, LuPlay } from 'react-icons/lu'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { audioUrl } from '../api/conversations'
import AppealModal from '../components/detail/AppealModal'
import AudioPlayer from '../components/detail/AudioPlayer'
import CriterionCard from '../components/detail/CriterionCard'
import OperatorReportModal from '../components/detail/OperatorReportModal'
import ScoreSummary from '../components/detail/ScoreSummary'
import Transcript from '../components/detail/Transcript'
import ChannelBadge from '../components/dialogs/ChannelBadge'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Card, CardHeader } from '../components/ui/Card'
import { Select } from '../components/ui/Field'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { useEvaluationAppeals } from '../hooks/useAppeals'
import { useConversations } from '../hooks/useConversations'
import { useDialogDetail } from '../hooks/useDialogDetail'
import { useFormat } from '../hooks/useFormat'
import { useJob } from '../hooks/useJob'
import { AUDIO_LEAD_SEC } from '../lib/constants'

export default function DialogDetailPage() {
  const { t } = useTranslation()
  const format = useFormat()
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedEvaluation = Number(searchParams.get('evaluation')) || undefined
  const initialTurn = Number(searchParams.get('turn')) || null

  const { conversation, card, checklist, activeChecklist, isLoading, error } = useDialogDetail(id, requestedEvaluation)
  const { data: allConversations } = useConversations()
  const evaluationId = card.data?.evaluation.id
  const { data: appeals = [] } = useEvaluationAppeals(evaluationId)

  const audioRef = useRef(null)
  const [focus, setFocus] = useState(initialTurn ? { turn: initialTurn, nonce: 0 } : null)
  const [appealTarget, setAppealTarget] = useState(null)
  const [isReportOpen, setReportOpen] = useState(false)

  // Номера #N в доказательствах относятся к транскрипту, по которому оценивала модель (у звонков — распознанному)
  const turns = useMemo(() => card.data?.conversation?.transcript ?? conversation.data?.transcript ?? [], [card.data, conversation.data])
  const hasAudio = Boolean(conversation.data?.audio_url)
  const isExcluded = allConversations?.find((item) => item.id === id)?.excluded
  const evidence = useMemo(() => new Set((card.data?.final.criteria ?? []).flatMap((item) => item.evidence_ids ?? [])), [card.data])

  const selectEvaluation = useCallback(
    (nextId) => setSearchParams(nextId ? { evaluation: String(nextId) } : {}, { replace: true }),
    [setSearchParams],
  )
  const { job, isRunning, start } = useJob()
  const isAnalyzing = job?.status === 'running' && job.conversation_ids.includes(id)
  // Снимаем закреплённую оценку: после завершения страница покажет новый результат
  const runJob = (mode) => {
    selectEvaluation(null)
    start({ mode, conversationIds: [id] })
  }

  const goToTurn = useCallback(
    (turn) => {
      setFocus((previous) => ({ turn, nonce: (previous?.nonce ?? 0) + 1 }))
      setSearchParams(
        (params) => {
          params.set('turn', String(turn))
          return params
        },
        { replace: true },
      )
      const player = audioRef.current
      if (player) {
        player.currentTime = Math.max(0, (turns[turn - 1]?.offset_sec ?? 0) + AUDIO_LEAD_SEC)
        player.play().catch(() => {})
      }
    },
    [setSearchParams, turns],
  )

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={conversation.refetch} />

  const conv = conversation.data
  const result = card.data
  const isStale = result && activeChecklist && result.checklist.id !== activeChecklist.id
  const originalById = new Map(result?.original.criteria.map((item) => [item.id, item]))

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Link to="/dialogs" aria-label={t('detail.back')} className="flex size-10 items-center justify-center rounded-lg border border-line bg-surface hover:bg-surface-muted">
          <LuArrowLeft className="size-4" />
        </Link>
        <h1 className="text-xl font-bold">{conv.source_id ?? conv.id}</h1>
        <ChannelBadge channel={conv.channel} />
        <Badge>{conv.language}</Badge>
        {result?.conversation?.transcript_source === 'asr' && <Badge tone="info">{t('detail.transcriptAsr')}</Badge>}
        <span className="text-xs text-ink-muted">{t('detail.imported', { date: format.date(conv.imported_at) })}</span>
        <div className="flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto">
          {conv.evaluations.length > 1 && (
            <Select
              aria-label={t('detail.history')}
              value={evaluationId ?? ''}
              onChange={(event) => selectEvaluation(Number(event.target.value))}
              className="w-auto max-w-64"
            >
              {conv.evaluations.map((item) => (
                <option key={item.id} value={item.id}>
                  {t('detail.evaluationOption', { id: item.id, date: format.date(item.created_at) })}
                </option>
              ))}
            </Select>
          )}
          {result && (
            <Button
              icon={LuDownload}
              disabled={!result.operator_summary}
              title={result.operator_summary ? undefined : t('report.unavailable')}
              onClick={() => setReportOpen(true)}
            >
              {t('report.export')}
            </Button>
          )}
          {isExcluded ? (
            <Badge title={t('status.excludedHint')}>{t('status.excluded')}</Badge>
          ) : (
            <>
              {isStale && (
                <Button icon={LuListChecks} disabled={isRunning} onClick={() => runJob('reapply')}>
                  {t('detail.applyChecklist', { version: activeChecklist.version })}
                </Button>
              )}
              <Button variant="primary" icon={LuPlay} loading={isAnalyzing} disabled={isRunning} onClick={() => runJob('evaluate')}>
                {t(result ? 'detail.evaluateAgain' : 'detail.evaluate')}
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Transcript
          turns={turns}
          evidence={evidence}
          focus={focus}
          onPlay={hasAudio ? goToTurn : undefined}
          player={hasAudio ? <AudioPlayer ref={audioRef} src={audioUrl(conv.id)} sourceUrl={conv.audio_url} /> : null}
        />
        <div className="min-w-0 space-y-5">
          {result ? (
            <>
              <ScoreSummary card={result} />
              <Card>
                <CardHeader title={t('detail.criteria')} />
                {result.final.criteria.map((item) => (
                  <CriterionCard
                    key={item.id}
                    item={item}
                    original={originalById.get(item.id)}
                    criterion={checklist?.criteria.find((criterion) => criterion.id === item.id)}
                    appeals={appeals.filter((appeal) => appeal.criterion_id === item.id)}
                    turns={turns}
                    onTurn={goToTurn}
                    onAppeal={setAppealTarget}
                  />
                ))}
              </Card>
            </>
          ) : (
            <Card>
              <EmptyState
                title={t('common.noData')}
                description={t(isExcluded ? 'status.excludedHint' : 'detail.notEvaluated')}
              />
            </Card>
          )}
        </div>
      </div>
      {isReportOpen && (
        <OperatorReportModal
          conversationId={conv.source_id ?? conv.id}
          summary={result.operator_summary}
          turns={turns}
          onClose={() => setReportOpen(false)}
        />
      )}
      {appealTarget && <AppealModal evaluationId={evaluationId} criterion={appealTarget} onClose={() => setAppealTarget(null)} />}
    </>
  )
}
