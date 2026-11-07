import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { importDataset, uploadDataset } from '../api/datasets'
import { useApiError } from './useApiError'
import { useDataset } from './useDataset'

const MAX_SHOWN_WARNINGS = 5

// Предупреждения импорта (вложения, пустые реплики, повторы id): первые пять, остальные одной строкой
function warningsText(warnings, t) {
  const shown = warnings.slice(0, MAX_SHOWN_WARNINGS)
  const rest = warnings.length - shown.length
  return [...shown, rest > 0 && t('import.moreWarnings', { count: rest })].filter(Boolean).join('\n')
}

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
      if (result.warnings?.length) {
        toast.warning(t('import.warnings', { count: result.warnings.length }), {
          description: warningsText(result.warnings, t),
          classNames: { description: 'whitespace-pre-line' },
          duration: 15000,
        })
      }
      onImported(result)
    },
    onError: notify,
  })
}
