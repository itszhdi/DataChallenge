import { useTranslation } from 'react-i18next'
import { LuSave } from 'react-icons/lu'
import { useAppSettingsForm } from '../../hooks/useAppSettings'
import Button from '../ui/Button'
import { Card, CardHeader } from '../ui/Card'
import { Checkbox, Field, Input, Select } from '../ui/Field'
import Slider from '../ui/Slider'
import { ErrorState, LoadingState } from '../ui/States'
import Switch from '../ui/Switch'

const QUEUE_SORTS = ['short_first', 'long_first', 'newest_first', 'oldest_first']
const MIN_THREADS = 1
const MAX_THREADS = 5
const MAX_DELAY_MS = 60000
const DELAY_STEP_MS = 100

export default function QueueSettings() {
  const { t } = useTranslation()
  const { settings, form, change, isDirty, save, isSaving } = useAppSettingsForm()

  if (settings.isLoading) return <LoadingState />
  if (settings.error) return <ErrorState error={settings.error} onRetry={settings.refetch} />

  return (
    <div className="space-y-5">
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Card className="pb-5">
          <CardHeader title={t('settings.queue.priorityTitle')} />
          <div className="space-y-4 px-5">
            <Field label={t('settings.queue.sort')}>
              <Select value={form.queue_sort} onChange={(event) => change('queue_sort', event.target.value)}>
                {QUEUE_SORTS.map((sort) => (
                  <option key={sort} value={sort}>
                    {t(`settings.queue.sort_${sort}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <fieldset className="space-y-2">
              <legend className="mb-1 text-xs font-medium text-ink-muted">{t('settings.queue.filter')}</legend>
              <Checkbox label={t('settings.queue.onlyMissing')} checked={form.only_missing} onChange={(value) => change('only_missing', value)} />
              <Checkbox
                label={t('settings.queue.includeErrors')}
                hint={t('settings.queue.includeErrorsHint')}
                checked={form.include_errors}
                onChange={(value) => change('include_errors', value)}
              />
            </fieldset>
          </div>
        </Card>

        <Card className="pb-5">
          <CardHeader title={t('settings.queue.performanceTitle')} />
          <div className="space-y-5 px-5">
            <div>
              <div className="mb-2 flex items-center justify-between text-xs font-medium text-ink-muted">
                <span>{t('settings.queue.concurrency')}</span>
                <span className="text-sm text-ink tabular-nums">{form.concurrency}</span>
              </div>
              <Slider
                label={t('settings.queue.concurrency')}
                value={form.concurrency}
                min={MIN_THREADS}
                max={MAX_THREADS}
                onChange={(value) => change('concurrency', value)}
              />
              <p className="mt-1 text-xs text-ink-muted">{t('settings.queue.concurrencyHint')}</p>
            </div>
            <Field label={t('settings.queue.delay')} hint={t('settings.queue.delayHint')}>
              <Input
                type="number"
                min={0}
                max={MAX_DELAY_MS}
                step={DELAY_STEP_MS}
                value={form.request_delay_ms}
                onChange={(event) => change('request_delay_ms', Math.min(MAX_DELAY_MS, Math.max(0, Number(event.target.value) || 0)))}
              />
            </Field>
            <Switch
              label={t('settings.queue.autoEvaluate')}
              hint={t('settings.queue.autoEvaluateHint')}
              checked={form.auto_evaluate_on_import}
              onChange={(value) => change('auto_evaluate_on_import', value)}
            />
          </div>
        </Card>
      </div>
      <div className="flex justify-end">
        <Button variant="primary" icon={LuSave} loading={isSaving} disabled={!isDirty} onClick={save}>
          {t('settings.save')}
        </Button>
      </div>
    </div>
  )
}
