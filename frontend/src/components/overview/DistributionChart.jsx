import { useTranslation } from 'react-i18next'
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useIsNarrow } from '../../hooks/useIsNarrow'
import { barOpacity, TONE_FILL, TOOLTIP_PROPS } from '../../lib/chartTheme'
import { Card, CardHeader } from '../ui/Card'
import TwoLineTick from './TwoLineTick'

const CHART_HEIGHT = 230
const X_AXIS_HEIGHT = 40
const BUCKET_TONE = { critical: 'danger', risk: 'warning', norm: 'info', reference: 'success' }

export default function DistributionChart({ distribution, filter, onFilter }) {
  const { t } = useTranslation()
  const isNarrow = useIsNarrow()
  const rows = distribution.map((row) => ({ ...row, label: t(`overview.bucket.${row.bucket}`) }))
  const selected = filter?.type === 'bucket' ? filter.value : null

  return (
    <Card className="pb-3">
      <CardHeader title={t('overview.distributionTitle')} hint={t('overview.distributionHint')} />
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart data={rows} margin={{ left: 12, right: 12, top: 20, bottom: 0 }}>
          <XAxis dataKey="label" height={X_AXIS_HEIGHT} tick={<TwoLineTick fontSize={isNarrow ? 10 : 12} />} tickLine={false} axisLine={false} interval={0} />
          <YAxis allowDecimals={false} hide />
          <Tooltip {...TOOLTIP_PROPS} formatter={(value) => [value, t('overview.dialogsCount')]} />
          <Bar
            dataKey="count"
            radius={[6, 6, 0, 0]}
            cursor="pointer"
            isAnimationActive={false}
            onClick={(entry) => {
              if (entry.payload.count) onFilter({ type: 'bucket', value: entry.payload.bucket, label: entry.payload.label })
            }}
          >
            {rows.map((row) => (
              <Cell key={row.bucket} fill={TONE_FILL[BUCKET_TONE[row.bucket]]} opacity={barOpacity(row.bucket === selected, Boolean(selected))} />
            ))}
            <LabelList dataKey="count" position="top" style={{ fill: 'var(--ink)', fontSize: 12, fontWeight: 600 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}
