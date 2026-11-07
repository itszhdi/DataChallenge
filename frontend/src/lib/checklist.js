const TOTAL_WEIGHT = 100
const MIN_SCALE_STEPS = 2
const DEFAULT_SCALE = [10, 5, 0].map((value) => ({ value, description: '' }))

const isScored = (criterion) => criterion.type !== 'flag'

export const weightTotal = (criteria) =>
  criteria.filter(isScored).reduce((sum, criterion) => sum + (Number(criterion.weight) || 0), 0)

// Метод наибольших остатков: целые веса пропорционально текущим, сумма ровно 100
export function autoBalance(criteria) {
  const scored = criteria.filter(isScored)
  const total = weightTotal(criteria)
  const shares = scored.map((criterion) => ({
    id: criterion.id,
    exact: total > 0 ? (criterion.weight / total) * TOTAL_WEIGHT : TOTAL_WEIGHT / scored.length,
  }))
  const weights = new Map(shares.map((share) => [share.id, Math.floor(share.exact)]))
  const left = TOTAL_WEIGHT - [...weights.values()].reduce((sum, weight) => sum + weight, 0)
  ;[...shares]
    .sort((a, b) => b.exact - Math.floor(b.exact) - (a.exact - Math.floor(a.exact)))
    .slice(0, left)
    .forEach((share) => weights.set(share.id, weights.get(share.id) + 1))
  return criteria.map((criterion) => (weights.has(criterion.id) ? { ...criterion, weight: weights.get(criterion.id) } : criterion))
}

export function createCriterion(checklist, title) {
  const ids = new Set(checklist.criteria.map((criterion) => criterion.id))
  let number = checklist.criteria.length + 1
  while (ids.has(`c${String(number).padStart(2, '0')}_custom`)) number += 1
  return {
    id: `c${String(number).padStart(2, '0')}_custom`,
    section: checklist.sections[0]?.id ?? 'main',
    title,
    type: 'binary',
    weight: 0,
    na_allowed: false,
    na_condition: '',
    rule: '',
    scale: [],
    guidance: '',
    examples_pass: [],
    examples_fail: [],
    flag_types: [],
  }
}

// Смена типа приводит критерий к правилам бэкенда: флаг без баллов и N/A, шкала со ступенями
export function withType(criterion, type) {
  if (type === 'flag') return { ...criterion, type, weight: 0, na_allowed: false, na_condition: '', scale: [] }
  if (type === 'scale') return { ...criterion, type, scale: criterion.scale.length ? criterion.scale : DEFAULT_SCALE }
  return { ...criterion, type, scale: [] }
}

function criterionErrors(criterion) {
  const errors = {}
  if (!criterion.title.trim()) errors.title = 'title'
  if (criterion.type !== 'scale' && !criterion.rule.trim()) errors.rule = 'rule'
  if (criterion.na_allowed && !criterion.na_condition.trim()) errors.na_condition = 'naCondition'
  if (criterion.type === 'scale') {
    const values = criterion.scale.map((step) => step.value)
    const isValid =
      values.length >= MIN_SCALE_STEPS &&
      values.every(Number.isInteger) &&
      new Set(values).size === values.length &&
      Math.max(...values) > 0
    if (!isValid) errors.scale = 'scale'
  }
  return errors
}

export const validateChecklist = (checklist) =>
  Object.fromEntries(
    checklist.criteria.map((criterion) => [criterion.id, criterionErrors(criterion)]).filter(([, errors]) => Object.keys(errors).length),
  )
