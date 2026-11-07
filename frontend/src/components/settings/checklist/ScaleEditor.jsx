import { useTranslation } from 'react-i18next'
import { LuPlus, LuTrash2 } from 'react-icons/lu'
import Button from '../../ui/Button'
import { Input } from '../../ui/Field'

const toStepValue = (raw) => (raw === '' ? '' : Number(raw))

export default function ScaleEditor({ steps, onChange, error }) {
  const { t } = useTranslation()
  const updateStep = (index, change) => onChange(steps.map((step, position) => (position === index ? { ...step, ...change } : step)))

  return (
    <fieldset>
      <legend className="mb-1 text-xs font-medium text-ink-muted">{t('settings.field.scale')}</legend>
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div key={index} className="flex items-center gap-2">
            <Input
              type="number"
              aria-label={t('settings.field.stepValue')}
              value={step.value}
              onChange={(event) => updateStep(index, { value: toStepValue(event.target.value) })}
              className="w-20! shrink-0"
            />
            <Input
              aria-label={t('settings.field.stepDescription')}
              placeholder={t('settings.field.stepDescription')}
              value={step.description}
              onChange={(event) => updateStep(index, { description: event.target.value })}
            />
            <Button
              variant="ghost"
              size="icon"
              icon={LuTrash2}
              aria-label={t('settings.field.removeStep')}
              onClick={() => onChange(steps.filter((_, position) => position !== index))}
            />
          </div>
        ))}
      </div>
      {error && <p className="mt-1 text-xs text-danger-text">{error}</p>}
      <Button size="sm" icon={LuPlus} className="mt-2" onClick={() => onChange([...steps, { value: '', description: '' }])}>
        {t('settings.field.addStep')}
      </Button>
    </fieldset>
  )
}
