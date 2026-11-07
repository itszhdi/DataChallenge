import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchActiveChecklist, fetchDefaultChecklist, saveChecklist } from '../api/checklists'
import { autoBalance, createCriterion } from '../lib/checklist'
import { useApiError } from './useApiError'

// Черновик живёт поверх активной версии: пока правок нет, показываем то, что на бэкенде
export function useChecklistDraft({ onSaved, onDefaultLoaded }) {
  const queryClient = useQueryClient()
  const { notify } = useApiError()
  const active = useQuery({ queryKey: ['checklist', 'active'], queryFn: fetchActiveChecklist })
  const [edited, setEdited] = useState(null)
  const draft = edited ?? active.data?.data ?? null

  const updateCriteria = (update) => setEdited({ ...draft, criteria: update(draft.criteria) })

  const save = useMutation({
    mutationFn: () => saveChecklist({ data: draft, comment: '' }),
    onSuccess: (result) => {
      setEdited(null)
      queryClient.invalidateQueries({ queryKey: ['checklist'] })
      onSaved(result)
    },
    onError: notify,
  })

  const loadDefault = useMutation({
    mutationFn: fetchDefaultChecklist,
    onSuccess: (data) => {
      setEdited(data)
      onDefaultLoaded()
    },
    onError: notify,
  })

  return {
    active,
    draft,
    isDirty: edited !== null,
    updateCriterion: (id, change) =>
      updateCriteria((criteria) => criteria.map((criterion) => (criterion.id === id ? { ...criterion, ...change } : criterion))),
    addCriterion: (title) => {
      const criterion = createCriterion(draft, title)
      updateCriteria((criteria) => [...criteria, criterion])
      return criterion.id
    },
    removeCriterion: (id) => updateCriteria((criteria) => criteria.filter((criterion) => criterion.id !== id)),
    balanceWeights: () => updateCriteria(autoBalance),
    discard: () => setEdited(null),
    save,
    loadDefault,
  }
}
