import { useQuery } from '@tanstack/react-query'
import { fetchConversations } from '../api/conversations'

export const useConversations = (dataset, refetchInterval = false) =>
  useQuery({ queryKey: ['conversations', dataset ?? ''], queryFn: () => fetchConversations(dataset), refetchInterval })
