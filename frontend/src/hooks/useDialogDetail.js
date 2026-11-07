import { useQuery } from '@tanstack/react-query'
import { fetchActiveChecklist, fetchChecklist } from '../api/checklists'
import { fetchConversation } from '../api/conversations'
import { fetchEvaluation } from '../api/evaluations'

export function useDialogDetail(id, requestedEvaluationId) {
  const conversation = useQuery({ queryKey: ['conversation', id], queryFn: () => fetchConversation(id) })
  const evaluationId = requestedEvaluationId ?? conversation.data?.evaluations[0]?.id
  const card = useQuery({
    queryKey: ['evaluation', evaluationId],
    queryFn: () => fetchEvaluation(evaluationId),
    enabled: Boolean(evaluationId),
  })
  const checklistId = card.data?.checklist.id
  const checklist = useQuery({
    queryKey: ['checklist', checklistId],
    queryFn: () => fetchChecklist(checklistId),
    enabled: Boolean(checklistId),
  })
  const activeChecklist = useQuery({ queryKey: ['checklist', 'active'], queryFn: fetchActiveChecklist })

  return {
    conversation,
    card,
    checklist: checklist.data?.data,
    activeChecklist: activeChecklist.data,
    isLoading: conversation.isLoading || (Boolean(evaluationId) && card.isLoading),
    error: conversation.error ?? card.error,
  }
}
