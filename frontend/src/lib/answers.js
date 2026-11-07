// Подпись и цвет ответа критерия; item — элемент score.criteria с бэкенда
export function answerLabel(item, scaleMax, t) {
  if (!item || item.status === 'error') return t('answer.missing')
  if (item.na) return t('answer.na')
  if (item.type === 'scale') return `${item.value} / ${scaleMax ?? '—'}`
  if (item.type === 'flag') return t(item.value === 1 ? 'answer.detected' : 'answer.notDetected')
  return t(item.value === 1 ? 'answer.yes' : 'answer.no')
}

export function answerTone(item, scaleMax) {
  if (!item || item.status === 'error') return 'warning'
  if (item.na) return 'neutral'
  if (item.type === 'flag') return item.value === 1 ? 'danger' : 'success'
  if (item.type === 'scale') {
    if (item.value === scaleMax) return 'success'
    return item.value === 0 ? 'danger' : 'warning'
  }
  return item.value === 1 ? 'success' : 'danger'
}

export const scaleMaxOf = (criterion) =>
  criterion?.scale?.length ? Math.max(...criterion.scale.map((step) => step.value)) : null
