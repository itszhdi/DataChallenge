import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import DatasetSelect from '../components/layout/DatasetSelect'
import PageHeader from '../components/layout/PageHeader'
import CriteriaChart from '../components/overview/CriteriaChart'
import DistributionChart from '../components/overview/DistributionChart'
import DrilldownTable from '../components/overview/DrilldownTable'
import KpiCards from '../components/overview/KpiCards'
import RiskMonitor from '../components/overview/RiskMonitor'
import SegmentsChart from '../components/overview/SegmentsChart'
import { Card } from '../components/ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { useDashboard } from '../hooks/useDashboard'
import { useDataset } from '../hooks/useDataset'

export default function OverviewPage() {
  const { t } = useTranslation()
  const { dataset } = useDataset()
  const { data, isLoading, error, refetch } = useDashboard(dataset)
  const [filter, setFilter] = useState(null)
  const tableRef = useRef(null)

  // Повторный клик снимает фильтр; новый фильтр сразу показывает таблицу с результатом
  const toggleFilter = useCallback((next) => {
    setFilter((current) => (current?.type === next.type && current?.value === next.value ? null : next))
    tableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const renderContent = () => {
    if (isLoading) return <LoadingState />
    if (error) return <ErrorState error={error} onRetry={refetch} />
    if (!data.summary.total_evaluated) {
      return (
        <Card>
          <EmptyState title={t('common.noData')} description={t('overview.empty')}>
            <Link to="/dialogs" className="mt-2 text-sm font-medium text-brand-text underline">
              {t('nav.dialogs')}
            </Link>
          </EmptyState>
        </Card>
      )
    }
    return (
      <div className="space-y-5">
        <KpiCards data={data} filter={filter} onFilter={toggleFilter} />
        {/* Два ряда по две карточки одной высоты: графики растягиваются, пустот под короткими блоками нет */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <CriteriaChart criteria={data.criteria_averages} filter={filter} onFilter={toggleFilter} />
          <SegmentsChart byLanguage={data.by_language} byChannel={data.by_channel} filter={filter} onFilter={toggleFilter} />
          <DistributionChart distribution={data.distribution} filter={filter} onFilter={toggleFilter} />
          <RiskMonitor dialogs={data.dialogs} filter={filter} onFilter={toggleFilter} />
        </div>
        <DrilldownTable ref={tableRef} data={data} filter={filter} onReset={() => setFilter(null)} />
      </div>
    )
  }

  return (
    <>
      <PageHeader title={t('nav.overview')} description={t('overview.description')} actions={<DatasetSelect />} />
      {renderContent()}
    </>
  )
}
