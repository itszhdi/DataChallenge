import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchConversations } from '../api/conversations'
import { evaluateConversation } from '../api/evaluations'
import { useApiError } from './useApiError'

export const useConversations = (dataset) =>
  useQuery({ queryKey: ['conversations', dataset ?? ''], queryFn: () => fetchConversations(dataset) })

export function useEvaluateConversation({ onEvaluated } = {}) {
  const queryClient = useQueryClient()
  const { notify } = useApiError()
  return useMutation({
    mutationFn: evaluateConversation,
    onSuccess: (card) => {
      queryClient.invalidateQueries()
      onEvaluated?.(card)
    },
    onError: notify,
  })
}
