import { getCoreRowModel, getPaginationRowModel, getSortedRowModel, useReactTable } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuPlay } from 'react-icons/lu'
import { useNavigate } from 'react-router-dom'
import { useFormat } from '../../hooks/useFormat'
import { PAGE_SIZE } from '../../lib/constants'
import { formatClock, scoreTone } from '../../lib/format'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import DataTable from '../ui/DataTable'
import ChannelBadge from './ChannelBadge'

// Состояние строки по приоритету: живая задача → статус в БД (переживает F5, виден авто-воркер) → результат оценки
function rowState(row, live, failure, position) {
  const withEta = row.eta_sec ? ` · ~${formatClock(row.eta_sec)}` : ''
  const persisted = live ? null : row.status
  if (live === 'analyzing' || persisted === 'running') return { tone: 'info', key: 'status.analyzing', suffix: withEta }
  if (live === 'queued' || persisted === 'queued') return { tone: 'info', key: 'status.queued', suffix: withEta }
  if (failure) return { tone: 'danger', key: 'status.failed', title: { key: `jobError.${failure}.title` } }
  if (row.status === 'failed') return { tone: 'danger', key: 'status.failed', title: row.status_error }
  if (!row.last_evaluation_id && row.status === 'skipped') return { key: 'status.skipped', title: row.status_error }
  if (!row.last_evaluation_id && position) return { tone: 'info', key: 'status.upcoming', params: { position }, suffix: withEta }
  if (row.excluded) return { key: 'status.excluded', title: { key: 'status.excludedHint' } }
  if (!row.last_evaluation_id) return { key: 'status.notEvaluated' }
  if (row.gross_error) return { tone: 'danger', key: 'status.gross' }
  if (row.preliminary) return { tone: 'warning', key: 'status.preliminary' }
  return { tone: 'success', key: 'status.evaluated' }
}

function DialogStatus({ row, statuses, failures, upcoming }) {
  const { t } = useTranslation()
  const state = rowState(row, statuses.get(row.id), failures.get(row.id), upcoming.get(row.id))
  const title = state.title?.key ? t(state.title.key, { defaultValue: '' }) : state.title
  return (
    <Badge tone={state.tone} title={title || undefined}>
      {t(state.key, state.params)}
      {state.suffix}
    </Badge>
  )
}

const INITIAL_SORTING = [{ id: 'imported_at', desc: true }]

export default function DialogsTable({ rows, statuses, failures, upcoming, isBusy, onEvaluate }) {
  const { t } = useTranslation()
  const format = useFormat()
  const navigate = useNavigate()
  const [sorting, setSorting] = useState(INITIAL_SORTING)
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: PAGE_SIZE })
  // Фильтр мог сократить список: страница не должна выйти за его конец
  const lastPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1)

  const columns = useMemo(
    () => [
      { id: 'id', accessorFn: (row) => row.source_id ?? row.id, header: t('table.id'), cell: ({ getValue }) => <b>{getValue()}</b> },
      {
        accessorKey: 'channel',
        header: t('table.format'),
        cell: ({ getValue }) => <ChannelBadge channel={getValue()} />,
      },
      { accessorKey: 'language', header: t('table.language') },
      { accessorKey: 'messages', header: t('table.length') },
      {
        accessorKey: 'imported_at',
        header: t('table.importedAt'),
        cell: ({ getValue }) => format.date(getValue()),
      },
      {
        id: 'total',
        accessorFn: (row) => row.total ?? undefined,
        sortUndefined: 'last',
        header: t('table.total'),
        cell: ({ getValue }) => <Badge tone={scoreTone(getValue())}>{format.number(getValue())}</Badge>,
      },
      {
        id: 'status',
        enableSorting: false,
        header: t('table.status'),
        cell: ({ row }) => <DialogStatus row={row.original} statuses={statuses} failures={failures} upcoming={upcoming} />,
      },
      {
        accessorKey: 'open_appeals',
        header: t('table.appeals'),
        cell: ({ getValue }) => (getValue() ? <Badge tone="warning">{getValue()}</Badge> : '—'),
      },
      {
        id: 'action',
        enableSorting: false,
        header: t('table.action'),
        cell: ({ row: { original } }) => (
          <Button
            size="sm"
            icon={LuPlay}
            loading={statuses.get(original.id) === 'analyzing'}
            disabled={original.excluded || isBusy}
            onClick={(event) => {
              event.stopPropagation()
              onEvaluate(original.id)
            }}
          >
            {t(original.status === 'failed' ? 'dialogs.retry' : original.last_evaluation_id ? 'dialogs.reevaluate' : 'dialogs.evaluate')}
          </Button>
        ),
      },
    ],
    [t, format, statuses, failures, upcoming, isBusy, onEvaluate],
  )

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, pagination: { ...pagination, pageIndex: Math.min(pagination.pageIndex, lastPage) } },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getRowId: (row) => row.id,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: false,
  })

  return <DataTable table={table} onRowClick={(row) => navigate(`/dialogs/${encodeURIComponent(row.id)}`)} />
}
