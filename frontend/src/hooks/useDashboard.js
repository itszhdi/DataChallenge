import { useQuery } from '@tanstack/react-query'
import { fetchDashboard } from '../api/analytics'

export const useDashboard = (dataset) =>
  useQuery({ queryKey: ['dashboard', dataset ?? ''], queryFn: () => fetchDashboard(dataset) })
