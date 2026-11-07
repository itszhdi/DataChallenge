import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuPlugZap, LuSave } from 'react-icons/lu'
import { checkDatasetSource } from '../../api/datasets'
import { useApiError } from '../../hooks/useApiError'
import { useAppSettingsForm } from '../../hooks/useAppSettings'
import Button from '../ui/Button'
import { Card, CardHeader } from '../ui/Card'
import { Field, Input } from '../ui/Field'
import { ErrorState, LoadingState } from '../ui/States'

function CheckResult({ check }) {
  const { t } = useTranslation()
  const { describe } = useApiError()
  if (check.isIdle || check.isPending) return null
  const records = check.data?.total_records
  let message = describe(check.error)
  let tone = 'bg-danger-soft text-danger-text'
  if (check.isSuccess) {
    message = t(records ? 'settings.integration.ok' : 'settings.integration.empty', { dataset: check.data.dataset, count: records })
    tone = records ? 'bg-brand-soft text-brand-text' : 'bg-warn-soft text-warn-text'
  }
  return (
    <p role="status" className={clsx('rounded-xl p-3 text-sm', tone)}>
      {message}
    </p>
  )
}

export default function IntegrationSettings() {
  const { t } = useTranslation()
  const { settings, form, change, isDirty, save, isSaving } = useAppSettingsForm()
  const check = useMutation({ mutationFn: checkDatasetSource })

  if (settings.isLoading) return <LoadingState />
  if (settings.error) return <ErrorState error={settings.error} onRetry={settings.refetch} />

  const groupId = form.default_group_id.trim()
  return (
    <Card className="max-w-2xl pb-5">
      <CardHeader title={t('settings.integration.title')} hint={t('settings.integration.hint')} />
      <div className="space-y-4 px-5">
        <Field label={t('settings.integration.groupId')} hint={t('settings.integration.groupIdHint')}>
          <Input
            value={form.default_group_id}
            maxLength={64}
            onChange={(event) => {
              check.reset()
              change('default_group_id', event.target.value)
            }}
          />
        </Field>
        <div className="grid gap-2 sm:flex">
          <Button icon={LuPlugZap} loading={check.isPending} disabled={!groupId} onClick={() => check.mutate(groupId)}>
            {t('settings.integration.check')}
          </Button>
          <Button variant="primary" icon={LuSave} loading={isSaving} disabled={!isDirty || !groupId} onClick={save}>
            {t('settings.save')}
          </Button>
        </div>
        <CheckResult check={check} />
      </div>
    </Card>
  )
}
