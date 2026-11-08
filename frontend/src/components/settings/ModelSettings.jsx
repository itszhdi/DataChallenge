import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuPlugZap, LuSave } from 'react-icons/lu'
import { checkModels } from '../../api/settings'
import { useApiError } from '../../hooks/useApiError'
import { useAppSettingsForm } from '../../hooks/useAppSettings'
import Button from '../ui/Button'
import { Card, CardHeader } from '../ui/Card'
import { Field, Select } from '../ui/Field'

const PROFILES = ['gemini', 'luna', 'local']
const CALL_TRANSCRIPTS = ['asr', 'original']

function profileState(result, t) {
  if (!result.available) return { tone: 'bg-danger-soft text-danger-text', text: t('settings.model.unavailable', { error: result.error ?? '' }) }
  if (result.model_loaded === false) return { tone: 'bg-warn-soft text-warn-text', text: t('settings.model.notLoaded') }
  return { tone: 'bg-brand-soft text-brand-text', text: t('settings.model.available') }
}

// Выбор модели применяется сразу после сохранения, без рестарта бэкенда
export default function ModelSettings() {
  const { t } = useTranslation()
  const { describe } = useApiError()
  const { form, change, isDirty, save, isSaving } = useAppSettingsForm()
  const check = useMutation({ mutationFn: checkModels })
  if (!form) return null

  return (
    <Card className="max-w-2xl pb-5">
      <CardHeader title={t('settings.model.title')} hint={t('settings.model.hint')} />
      <div className="space-y-4 px-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('settings.model.profile')}>
            <Select value={form.llm_profile} onChange={(event) => change('llm_profile', event.target.value)}>
              {PROFILES.map((name) => (
                <option key={name} value={name}>
                  {t(`settings.model.profile_${name}`)} · {form.profiles?.[name]?.model}
                </option>
              ))}
            </Select>
          </Field>
          {/* Распознавание звонков выключено в .env (TRANSCRIBE_ENABLED) — выбирать транскрипт незачем */}
          {form.transcribe_enabled && (
            <Field label={t('settings.model.callTranscript')} hint={t('settings.model.callTranscriptHint')}>
              <Select value={form.call_transcript} onChange={(event) => change('call_transcript', event.target.value)}>
                {CALL_TRANSCRIPTS.map((value) => (
                  <option key={value} value={value}>
                    {t(`settings.model.transcript_${value}`)}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </div>
        <div className="grid gap-2 sm:flex">
          <Button icon={LuPlugZap} loading={check.isPending} onClick={() => check.mutate()}>
            {t('settings.model.check')}
          </Button>
          <Button variant="primary" icon={LuSave} loading={isSaving} disabled={!isDirty} onClick={save}>
            {t('settings.save')}
          </Button>
        </div>
        {check.isError && (
          <p role="status" className="rounded-xl bg-danger-soft p-3 text-sm text-danger-text">
            {describe(check.error)}
          </p>
        )}
        {check.isSuccess && (
          <ul role="status" className="space-y-2">
            {PROFILES.filter((name) => check.data[name]).map((name) => {
              const { tone, text } = profileState(check.data[name], t)
              return (
                <li key={name} className={clsx('rounded-xl p-3 text-sm', tone)}>
                  <b>{t(`settings.model.profile_${name}`)}</b> · {check.data[name].model}: {text}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Card>
  )
}
