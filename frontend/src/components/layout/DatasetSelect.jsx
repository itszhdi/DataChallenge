import { useTranslation } from 'react-i18next'
import { useDataset } from '../../hooks/useDataset'
import { Select } from '../ui/Field'

export default function DatasetSelect() {
  const { t } = useTranslation()
  const { dataset, datasets, setDataset } = useDataset()
  return (
    <Select
      aria-label={t('dataset.label')}
      value={dataset}
      onChange={(event) => setDataset(event.target.value)}
      className="w-full sm:w-auto sm:min-w-44"
    >
      <option value="">{t('dataset.all')}</option>
      {datasets.map((item) => (
        <option key={item.dataset} value={item.dataset}>
          {item.dataset} · {item.total}
        </option>
      ))}
    </Select>
  )
}
