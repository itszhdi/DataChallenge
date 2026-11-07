const LINE_HEIGHT = 14

// Подпись оси в две строки: первое слово и остаток. Подписи не наезжают друг на друга на узком экране
export default function TwoLineTick({ x, y, payload, fontSize = 12 }) {
  const [first, ...rest] = String(payload.value).split(' ')
  return (
    <text x={x} y={y + 12} textAnchor="middle" fill="var(--ink-muted)" fontSize={fontSize}>
      <tspan x={x}>{first}</tspan>
      {rest.length > 0 && (
        <tspan x={x} dy={LINE_HEIGHT}>
          {rest.join(' ')}
        </tspan>
      )}
    </text>
  )
}
