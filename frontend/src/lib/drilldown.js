// Фильтры drill-down: { type, value }. Критерий считается проваленным при неполном выполнении, N/A не входит
const PREDICATES = {
  gross: (row) => row.gross_error,
  // Тип нарушения c08; unknown — грубая ошибка без указанного типа
  grossType: (row, type) => row.gross_error && (type === 'unknown' ? !row.gross_types.length : row.gross_types.includes(type)),
  criterion: (row, id) => {
    const percent = row.criteria[id]?.percent
    return percent !== null && percent !== undefined && percent < 100
  },
  language: (row, value) => row.language === value,
  channel: (row, value) => row.channel === value,
  bucket: (row, value) => row.bucket === value,
}

export const applyDrilldown = (rows, filter) =>
  filter ? rows.filter((row) => PREDICATES[filter.type](row, filter.value)) : rows
