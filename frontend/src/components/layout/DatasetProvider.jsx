import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { fetchDatasets } from '../../api/datasets'
import { DatasetContext } from '../../hooks/useDataset'
import { useLocalStorage } from '../../hooks/useLocalStorage'
import { STORAGE_KEYS } from '../../lib/constants'

export default function DatasetProvider({ children }) {
  const [selected, setDataset] = useLocalStorage(STORAGE_KEYS.dataset, '')
  const { data: datasets = [] } = useQuery({ queryKey: ['datasets'], queryFn: fetchDatasets })
  // Сохранённый набор мог исчезнуть из БД: тогда показываем все наборы
  const dataset = datasets.length && !datasets.some((item) => item.dataset === selected) ? '' : selected
  const value = useMemo(() => ({ dataset, datasets, setDataset }), [dataset, datasets, setDataset])
  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>
}
