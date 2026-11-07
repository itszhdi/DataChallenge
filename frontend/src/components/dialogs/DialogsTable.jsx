import { getCoreRowModel, getPaginationRowModel, getSortedRowModel, useReactTable } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LuPlay } from 'react-icons/lu'
import { useNavigate } from 'react-router-dom'
import { useFormat } from '../../hooks/useFormat'
import { PAGE_SIZE } from '../../lib/constants'
import { scoreTone } from '../../lib/format'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import DataTable from '../ui/DataTable'
import ChannelBadge from './ChannelBadge'

function DialogStatus({ row, statuses, failures }) {
  const { t } = useTranslation()
  const status = statuses.get(row.id)
  const failure = failures.get(row.id)
  if (status === 'analyzing' || (!status && row.status === 'running')) return <Badge tone="info">{t('status.analyzing')}</Badge>
  if (status === 'queued' || (!status && row.status === 'queued')) return <Badge tone="info">{t('status.queued')}</Badge>
  if (failure) return <Badge tone="danger" title={t(`jobError.${failure}.title`, { defaultValue: '' })}>{t('status.failed')}</Badge>
  // Статус из БД переживает перезагрузку страницы и показывает работу авто-воркера
  if (row.status === 'failed') return <Badge tone="danger" title={row.status_error ?? undefined}>{t('status.failed')}</Badge>
  if (row.status === 'skipped' && !row.last_evaluation_id) return <Badge title={row.status_error ?? undefined}>{t('status.skipped')}</Badge>
  if (row.excluded) return <Badge title={t('status.excludedHint')}>{t('status.excluded')}</Badge>
  if (!row.last_evaluation_id) return <Badge>{t('status.notEvaluated')}</Badge>
  if (row.gross_error) return <Badge tone="danger">{t('status.gross')}</Badge>
  if (row.preliminary) return <Badge tone="warning">{t('status.preliminary')}</Badge>
  return <Badge tone="success">{t('status.evaluated')}</Badge>
}

const INITIAL_SORTING = [{ id: 'imported_at', desc: true }]

export default function DialogsTable({ rows, statuses, failures, isBusy, onEvaluate }) {
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
        cell: ({ row }) => <DialogStatus row={row.original} statuses={statuses} failures={failures} />,
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
            {t(original.last_evaluation_id ? 'dialogs.reevaluate' : 'dialogs.evaluate')}
          </Button>
        ),
      },
    ],
    [t, format, statuses, failures, isBusy, onEvaluate],
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
