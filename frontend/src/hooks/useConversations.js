import { useQuery } from '@tanstack/react-query'
import { fetchConversations } from '../api/conversations'

export const useConversations = (dataset) =>
  useQuery({ queryKey: ['conversations', dataset ?? ''], queryFn: () => fetchConversations(dataset) })
