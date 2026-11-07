import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useFormat } from '../../hooks/useFormat'
import { useIsNarrow } from '../../hooks/useIsNarrow'
import { barOpacity, TONE_FILL, TOOLTIP_PROPS } from '../../lib/chartTheme'
import { CHANNEL_LABEL_KEYS, CHANNELS, LANGUAGES } from '../../lib/constants'
import { Card, CardHeader } from '../ui/Card'
import TwoLineTick from './TwoLineTick'

const CHART_HEIGHT = 230
const X_AXIS_HEIGHT = 40

// Известные сегменты показываются всегда: пустой сегмент явно отмечается как «нет данных», а не 0
function buildRows(byLanguage, byChannel, t) {
  const segment = (type, value, stats, name) => ({
    key: `${type}:${value}`,
    type,
    value,
    label: stats ? name : `${name} (${t('common.noDataShort')})`,
    avg: stats?.avg_total ?? null,
    count: stats?.count ?? 0,
    fill: TONE_FILL[type === 'language' ? 'success' : 'info'],
  })
  const languages = [...new Set([...LANGUAGES, ...Object.keys(byLanguage)])]
  const channels = [...new Set([...CHANNELS, ...Object.keys(byChannel)])]
  return [
    ...languages.map((value) => segment('language', value, byLanguage[value], value)),
    ...channels.map((value) => segment('channel', value, byChannel[value], t(CHANNEL_LABEL_KEYS[value] ?? value))),
  ]
}

export default function SegmentsChart({ byLanguage, byChannel, filter, onFilter }) {
  const { t } = useTranslation()
  const isNarrow = useIsNarrow()
  const format = useFormat()
  const rows = useMemo(() => buildRows(byLanguage, byChannel, t), [byLanguage, byChannel, t])
  const hasSelection = filter?.type === 'language' || filter?.type === 'channel'

  return (
    <Card className="pb-3">
      <CardHeader title={t('overview.segmentsTitle')} hint={t('overview.segmentsHint')} />
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart data={rows} margin={{ left: 12, right: 12, top: 20, bottom: 0 }}>
          <XAxis dataKey="label" height={X_AXIS_HEIGHT} tick={<TwoLineTick fontSize={isNarrow ? 10 : 12} />} tickLine={false} axisLine={false} interval={0} />
          <YAxis domain={[0, 100]} hide />
          <Tooltip
            {...TOOLTIP_PROPS}
            formatter={(value, name, { payload }) => [format.number(value), t('overview.segmentTooltip', { count: payload.count })]}
          />
          <Bar
            dataKey={(row) => row.avg}
            radius={[6, 6, 0, 0]}
            cursor="pointer"
            isAnimationActive={false}
            onClick={(entry) => {
              const row = entry.payload
              if (row.count) onFilter({ type: row.type, value: row.value, label: row.label })
            }}
          >
            {rows.map((row) => (
              <Cell key={row.key} fill={row.fill} opacity={barOpacity(filter?.type === row.type && filter?.value === row.value, hasSelection)} />
            ))}
            <LabelList
              dataKey={(row) => row.avg}
              position="top"
              formatter={format.number}
              style={{ fill: 'var(--ink)', fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}
