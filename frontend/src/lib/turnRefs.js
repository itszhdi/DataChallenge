const TURN_REF = /#(\d+)/g

// Разбивает текст на фрагменты и ссылки вида #N на реплики диалога
export function splitTurnRefs(text, turnCount) {
  const parts = []
  let cursor = 0
  for (const match of String(text ?? '').matchAll(TURN_REF)) {
    const turn = Number(match[1])
    if (turn < 1 || turn > turnCount) continue
    if (match.index > cursor) parts.push({ text: text.slice(cursor, match.index) })
    parts.push({ text: match[0], turn })
    cursor = match.index + match[0].length
  }
  if (cursor < String(text ?? '').length) parts.push({ text: text.slice(cursor) })
  return parts
}
