// Группа статуса диалога по данным из БД: общая для фильтра на странице и сортировки колонки «Статус»
export const STATUS_FILTERS = ['gross', 'appeal', 'evaluated', 'preliminary', 'notEvaluated', 'inProgress', 'failed']

// Порядок сортировки: сначала то, что требует внимания
const RANK = { gross: 0, failed: 1, preliminary: 2, evaluated: 3, inProgress: 4, notEvaluated: 5 }

export function statusGroup(row) {
  if (row.status === 'running' || row.status === 'queued') return 'inProgress'
  if (row.status === 'failed' || (!row.last_evaluation_id && row.status === 'skipped')) return 'failed'
  if (!row.last_evaluation_id) return 'notEvaluated'
  if (row.gross_error) return 'gross'
  if (row.preliminary) return 'preliminary'
  return 'evaluated'
}

export const statusRank = (row) => RANK[statusGroup(row)]

export const matchesStatus = (row, filter) => (filter === 'appeal' ? row.open_appeals > 0 : statusGroup(row) === filter)
