import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createAppeal, fetchAppeals, resolveAppeal } from '../api/appeals'
import { useApiError } from './useApiError'

export function useEvaluationAppeals(evaluationId) {
  return useQuery({
    queryKey: ['appeals'],
    queryFn: fetchAppeals,
    enabled: Boolean(evaluationId),
    select: (appeals) => appeals.filter((appeal) => appeal.evaluation_id === evaluationId),
  })
}

function useAppealMutation(mutationFn, onSuccess) {
  const queryClient = useQueryClient()
  const { notify } = useApiError()
  return useMutation({
    mutationFn,
    onSuccess: (result) => {
      queryClient.invalidateQueries()
      onSuccess?.(result)
    },
    onError: notify,
  })
}

export const useCreateAppeal = (onSuccess) => useAppealMutation(createAppeal, onSuccess)

export const useResolveAppeal = (onSuccess) => useAppealMutation(resolveAppeal, onSuccess)
