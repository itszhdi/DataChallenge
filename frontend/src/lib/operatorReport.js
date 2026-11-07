const CRITICAL = 'critical'

function strengthsBlock(items, title, t) {
  if (!items.length) return null
  return [t('report.strengths'), ...items.map((item) => `• ${title(item)}`)].join('\n')
}

function improvementLines(item, title, turns, t) {
  const name = item.priority === CRITICAL ? t('report.critical', { title: title(item) }) : title(item)
  const quotes = (item.evidence_ids ?? [])
    .map((turn) => turns[turn - 1])
    .filter(Boolean)
    .map((turn) => `  ${t('report.quote')}: #${turn.index} ${t(`speaker.${turn.speaker}`, { defaultValue: turn.speaker }).toLowerCase()}: ${turn.text}`)
  return [
    `• ${name}`,
    item.feedback && `  ${t('report.reason')}: ${item.feedback}`,
    item.action && `  ${t('report.nextTime')}: ${item.action}`,
    ...quotes,
  ].filter(Boolean)
}

function improvementsBlock(items, title, turns, t) {
  if (!items.length) return null
  return [t('report.improvements'), ...items.flatMap((item) => improvementLines(item, title, turns, t))].join('\n')
}

function reviewBlock(items, title, t) {
  if (!items.length) return null
  return [t('report.review'), ...items.map((item) => `• ${title(item)}`)].join('\n')
}

// Текст отчёта для оператора по сводке из карточки оценки и транскрипту
export function buildOperatorReport({ conversationId, summary, turns, criterionTitle, t }) {
  const title = (item) => criterionTitle(item.criterion_id, item.title)
  return [
    t('report.heading', { id: conversationId }),
    strengthsBlock(summary.strengths, title, t),
    improvementsBlock(summary.improvements, title, turns, t),
    reviewBlock(summary.review, title, t),
  ]
    .filter(Boolean)
    .join('\n\n')
}
