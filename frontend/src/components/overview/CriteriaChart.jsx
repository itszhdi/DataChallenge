import { useTranslation } from 'react-i18next'
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useFormat } from '../../hooks/useFormat'
import { useIsNarrow } from '../../hooks/useIsNarrow'
import { useLabels } from '../../hooks/useLabels'
import { AXIS_TICK, barOpacity, TONE_FILL, TOOLTIP_PROPS } from '../../lib/chartTheme'
import { scoreTone } from '../../lib/format'
import { Card, CardHeader } from '../ui/Card'

const ROW_HEIGHT = 46
const AXIS_WIDTH = { narrow: 150, wide: 210 }
const NARROW_TICK = { ...AXIS_TICK, fontSize: 10 }

export default function CriteriaChart({ criteria, filter, onFilter }) {
  const { t } = useTranslation()
  const format = useFormat()
  const labels = useLabels()
  const isNarrow = useIsNarrow()
  const rows = criteria.map((criterion) => ({ ...criterion, label: labels.criterion(criterion.id, criterion.title) }))
  const selected = filter?.type === 'criterion' ? filter.value : null

  return (
    <Card className="pb-3">
      <CardHeader title={t('overview.criteriaTitle')} hint={t('overview.criteriaHint')} />
      <ResponsiveContainer width="100%" height={rows.length * ROW_HEIGHT + 24}>
        <BarChart data={rows} layout="vertical" margin={{ left: isNarrow ? 8 : 16, right: 48, top: 0, bottom: 0 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis
            type="category"
            dataKey="label"
            width={isNarrow ? AXIS_WIDTH.narrow : AXIS_WIDTH.wide}
            tick={isNarrow ? NARROW_TICK : AXIS_TICK}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip {...TOOLTIP_PROPS} formatter={(value) => [format.percent(value), t('overview.fulfillment')]} />
          <Bar
            dataKey="avg_percent"
            radius={6}
            barSize={22}
            cursor="pointer"
            isAnimationActive={false}
            background={{ fill: 'var(--surface-muted)', radius: 6 }}
            onClick={(entry) => onFilter({ type: 'criterion', value: entry.payload.id, label: entry.payload.label })}
          >
            {rows.map((row) => (
              <Cell key={row.id} fill={TONE_FILL[scoreTone(row.avg_percent)]} opacity={barOpacity(row.id === selected, Boolean(selected))} />
            ))}
            <LabelList
              dataKey="avg_percent"
              position="right"
              formatter={format.percent}
              style={{ fill: 'var(--ink)', fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}
