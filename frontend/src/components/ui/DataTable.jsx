import { flexRender } from '@tanstack/react-table'
import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuArrowDown, LuArrowUp, LuChevronLeft, LuChevronRight, LuChevronsUpDown } from 'react-icons/lu'
import { useIsNarrow } from '../../hooks/useIsNarrow'
import Button from './Button'
import { Field, Select } from './Field'

const SORT_ICONS = { asc: LuArrowUp, desc: LuArrowDown, false: LuChevronsUpDown }

function HeaderCell({ header }) {
  const label = flexRender(header.column.columnDef.header, header.getContext())
  if (!header.column.getCanSort()) return label
  const sorted = header.column.getIsSorted()
  const Icon = SORT_ICONS[sorted]
  return (
    <button
      type="button"
      onClick={header.column.getToggleSortingHandler()}
      className={clsx('inline-flex items-center gap-1 hover:text-ink', sorted && 'text-ink')}
    >
      {label}
      <Icon className="size-3.5" />
    </button>
  )
}

const rowProps = (row, onRowClick) =>
  onRowClick && {
    tabIndex: 0,
    onClick: () => onRowClick(row.original),
    onKeyDown: (event) => {
      if (event.key === 'Enter' && event.target === event.currentTarget) onRowClick(row.original)
    },
  }

function WideTable({ table, onRowClick }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id} className="border-y border-line text-left text-xs text-ink-muted">
              {group.headers.map((header) => (
                <th key={header.id} scope="col" className="px-5 py-3 font-medium whitespace-nowrap">
                  <HeaderCell header={header} />
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              {...rowProps(row, onRowClick)}
              className={clsx('border-b border-line last:border-0', onRowClick && 'cursor-pointer hover:bg-surface-muted')}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-5 py-3 whitespace-nowrap">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// На телефоне строка становится карточкой «подпись: значение», а сортировка выбирается отдельным полем
function SortSelect({ table }) {
  const { t } = useTranslation()
  const [sorted] = table.getState().sorting
  const columns = table.getAllLeafColumns().filter((column) => column.getCanSort())
  return (
    <div className="border-y border-line px-4 py-3">
      <Field label={t('table.sortBy')}>
        <Select
          value={sorted ? `${sorted.id}:${sorted.desc}` : ''}
          onChange={(event) => {
            const [id, desc] = event.target.value.split(':')
            table.setSorting([{ id, desc: desc === 'true' }])
          }}
        >
          {columns.flatMap((column) =>
            [false, true].map((desc) => (
              <option key={`${column.id}:${desc}`} value={`${column.id}:${desc}`}>
                {column.columnDef.header} {desc ? '↓' : '↑'}
              </option>
            )),
          )}
        </Select>
      </Field>
    </div>
  )
}

function CompactRows({ table, onRowClick }) {
  return (
    <>
      <SortSelect table={table} />
      <div>
        {table.getRowModel().rows.map((row) => {
          const [primary, ...cells] = row.getVisibleCells()
          return (
            <div
              key={row.id}
              {...rowProps(row, onRowClick)}
              className={clsx('border-b border-line p-4 text-sm last:border-0', onRowClick && 'cursor-pointer active:bg-surface-muted')}
            >
              <div className="mb-2">{flexRender(primary.column.columnDef.cell, primary.getContext())}</div>
              <dl className="space-y-1.5">
                {cells.map((cell) => (
                  <div key={cell.id} className="flex items-center justify-between gap-3">
                    <dt className="text-xs text-ink-muted">{cell.column.columnDef.header}</dt>
                    <dd className="min-w-0 text-right break-words">{flexRender(cell.column.columnDef.cell, cell.getContext())}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )
        })}
      </div>
    </>
  )
}

export default function DataTable({ table, onRowClick }) {
  const { t } = useTranslation()
  const isNarrow = useIsNarrow()
  const Rows = isNarrow ? CompactRows : WideTable
  const { pageIndex } = table.getState().pagination
  return (
    <div>
      <Rows table={table} onRowClick={onRowClick} />
      {table.getPageCount() > 1 && (
        <nav className="flex items-center justify-between gap-3 px-5 py-3 text-sm text-ink-muted" aria-label={t('table.pagination')}>
          <Button size="sm" icon={LuChevronLeft} disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>
            {t('table.previous')}
          </Button>
          <span className="text-center">{t('table.page', { page: pageIndex + 1, total: table.getPageCount() })}</span>
          <Button size="sm" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>
            {t('table.next')}
            <LuChevronRight className="size-4" />
          </Button>
        </nav>
      )}
    </div>
  )
}
