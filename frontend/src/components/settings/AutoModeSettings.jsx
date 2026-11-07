import { useTranslation } from 'react-i18next'
import { LuSave } from 'react-icons/lu'
import { useAppSettingsForm } from '../../hooks/useAppSettings'
import { useDataset } from '../../hooks/useDataset'
import Button from '../ui/Button'
import { Card, CardHeader } from '../ui/Card'
import { Field, Select } from '../ui/Field'
import Switch from '../ui/Switch'

const AUTO_CALLS = ['mixed', 'first', 'last']

// Авто-воркер сам берёт неоценённые диалоги по одному; порядок — общая сортировка очереди выше
export default function AutoModeSettings() {
  const { t } = useTranslation()
  const { datasets } = useDataset()
  const { form, change, isDirty, save, isSaving } = useAppSettingsForm()
  if (!form) return null

  return (
    <Card className="pb-5">
      <CardHeader title={t('settings.auto.title')} hint={t('settings.auto.hint')} />
      <div className="space-y-4 px-5">
        <Switch label={t('settings.auto.mode')} hint={t('settings.auto.modeHint')} checked={form.auto_mode} onChange={(value) => change('auto_mode', value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('settings.auto.dataset')}>
            <Select value={form.auto_dataset ?? ''} onChange={(event) => change('auto_dataset', event.target.value || null)}>
              <option value="">{t('dataset.all')}</option>
              {datasets.map((item) => (
                <option key={item.dataset} value={item.dataset}>
                  {item.dataset}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('settings.auto.calls')}>
            <Select value={form.auto_calls} onChange={(event) => change('auto_calls', event.target.value)}>
              {AUTO_CALLS.map((value) => (
                <option key={value} value={value}>
                  {t(`settings.auto.calls_${value}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="flex justify-end">
          <Button variant="primary" icon={LuSave} loading={isSaving} disabled={!isDirty} onClick={save}>
            {t('settings.save')}
          </Button>
        </div>
      </div>
    </Card>
  )
}
