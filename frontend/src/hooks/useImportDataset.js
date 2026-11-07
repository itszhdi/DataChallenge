import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { importDataset, uploadDataset } from '../api/datasets'
import { useApiError } from './useApiError'
import { useDataset } from './useDataset'

export function useImportDataset(onImported) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { setDataset } = useDataset()
  const { notify } = useApiError()
  return useMutation({
    mutationFn: ({ file, groupId, url }) => (file ? uploadDataset(file) : importDataset({ groupId, url })),
    onSuccess: (result) => {
      setDataset(result.dataset)
      queryClient.invalidateQueries()
      toast.success(t('import.done', { count: result.imported, skipped: result.skipped, dataset: result.dataset }))
      onImported()
    },
    onError: notify,
  })
}
