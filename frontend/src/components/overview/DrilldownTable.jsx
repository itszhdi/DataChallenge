import { getCoreRowModel, getPaginationRowModel, getSortedRowModel, useReactTable } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuX } from 'react-icons/lu'
import { useNavigate } from 'react-router-dom'
import { useFormat } from '../../hooks/useFormat'
import { useLabels } from '../../hooks/useLabels'
import { PAGE_SIZE } from '../../lib/constants'
import { applyDrilldown } from '../../lib/drilldown'
import { scoreTone } from '../../lib/format'
import ChannelBadge from '../dialogs/ChannelBadge'
import Badge from '../ui/Badge'
import { Card, CardHeader } from '../ui/Card'
import DataTable from '../ui/DataTable'
import { EmptyState } from '../ui/States'

const INITIAL_SORTING = [{ id: 'total', desc: false }]

export default function DrilldownTable({ ref, data, filter, onReset }) {
  const { t } = useTranslation()
  const format = useFormat()
  const labels = useLabels()
  const navigate = useNavigate()
  const [sorting, setSorting] = useState(INITIAL_SORTING)
  const rows = useMemo(() => applyDrilldown(data.dialogs, filter), [data.dialogs, filter])

  const criterionTitle = useMemo(() => {
    const titles = new Map(data.criteria_averages.map((criterion) => [criterion.id, criterion.title]))
    return (id) => (id ? labels.criterion(id, titles.get(id) ?? id) : '—')
  }, [data.criteria_averages, labels])

  const columns = useMemo(
    () => [
      { accessorKey: 'conversation_id', header: t('table.id'), cell: ({ getValue }) => <b>{getValue()}</b> },
      { accessorKey: 'channel', header: t('table.format'), cell: ({ getValue }) => <ChannelBadge channel={getValue()} /> },
      { accessorKey: 'language', header: t('table.language') },
      {
        id: 'total',
        accessorFn: (row) => row.total ?? undefined,
        sortUndefined: 'last',
        header: t('table.total'),
        cell: ({ getValue }) => <Badge tone={scoreTone(getValue())}>{format.number(getValue())}</Badge>,
      },
      {
        accessorKey: 'gross_error',
        header: t('table.gross'),
        cell: ({ row: { original } }) =>
          original.gross_error ? (
            <Badge tone="danger">
              {original.gross_types.map((type) => t(`gross.${type}`, { defaultValue: type })).join(', ') || t('status.gross')}
            </Badge>
          ) : (
            '—'
          ),
      },
      {
        accessorKey: 'weak_criterion',
        enableSorting: false,
        header: t('table.weakCriterion'),
        cell: ({ getValue }) => criterionTitle(getValue()),
      },
    ],
    [t, format, criterionTitle],
  )

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getRowId: (row) => row.conversation_id,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: PAGE_SIZE } },
  })

  return (
    <div ref={ref} className="scroll-mt-20">
      <Card glass>
        <CardHeader
          title={t('overview.drilldownTitle')}
          hint={t('overview.drilldownHint', { count: rows.length })}
          actions={
            filter && (
              <button
                type="button"
                onClick={onReset}
                className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand-text"
              >
                {filter.label}
                <LuX className="size-3.5" aria-label={t('overview.resetFilter')} />
              </button>
            )
          }
        />
        {rows.length ? (
          <DataTable
            table={table}
            onRowClick={(row) => navigate(`/dialogs/${encodeURIComponent(row.conversation_id)}?evaluation=${row.evaluation_id}`)}
          />
        ) : (
          <EmptyState title={t('common.noData')} />
        )}
      </Card>
    </div>
  )
}
