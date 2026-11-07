import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { fetchSettings, updateSettings } from '../api/settings'
import { useApiError } from './useApiError'

export const useAppSettings = () => useQuery({ queryKey: ['settings'], queryFn: fetchSettings })

// Форма настроек: правки лежат поверх значений с бэкенда, вкладки сохраняют общий объект
export function useAppSettingsForm() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { notify } = useApiError()
  const settings = useAppSettings()
  const [edits, setEdits] = useState({})

  const save = useMutation({
    mutationFn: updateSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(['settings'], saved)
      setEdits({})
      toast.success(t('settings.saved'))
    },
    onError: notify,
  })

  const form = settings.data ? { ...settings.data, ...edits } : null
  return {
    settings,
    form,
    change: (field, value) => setEdits((current) => ({ ...current, [field]: value })),
    isDirty: Object.keys(edits).length > 0,
    save: () => save.mutate(form),
    isSaving: save.isPending,
  }
}
