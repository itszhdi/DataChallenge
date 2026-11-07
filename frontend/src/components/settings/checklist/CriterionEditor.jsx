import * as Accordion from '@radix-ui/react-accordion'
import { useTranslation } from 'react-i18next'
import { LuChevronDown, LuTrash2 } from 'react-icons/lu'
import { useLabels } from '../../../hooks/useLabels'
import { withType } from '../../../lib/checklist'
import Badge from '../../ui/Badge'
import Button from '../../ui/Button'
import { Checkbox, Field, Input, Select, Textarea } from '../../ui/Field'
import ScaleEditor from './ScaleEditor'

const CRITERION_TYPES = ['binary', 'scale', 'flag']
const MAX_WEIGHT = 100

const clampWeight = (raw) => Math.min(MAX_WEIGHT, Math.max(0, Number(raw) || 0))

const parseList = (raw) =>
  raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

export default function CriterionEditor({ criterion, position, sections, errors, canRemove, onChange, onRemove }) {
  const { t } = useTranslation()
  const labels = useLabels()
  const number = String(position).padStart(2, '0')
  const isFlag = criterion.type === 'flag'
  const errorText = (field) => errors?.[field] && t(`settings.validation.${errors[field]}`)
  const title = labels.criterion(criterion.id, criterion.title) || t('settings.checklist.untitled')

  return (
    <Accordion.Item value={criterion.id} className="border-b border-line last:border-0">
      <Accordion.Header className="flex items-center gap-2 pr-3">
        <Accordion.Trigger className="group flex min-w-0 flex-1 items-center gap-3 p-4 text-left">
          <LuChevronDown className="size-4 shrink-0 text-ink-muted transition-transform group-data-[state=open]:rotate-180" />
          <span className="min-w-0 flex-1 text-sm font-medium break-words hyphens-auto">
            {number}. {title}
          </span>
          {errors && <Badge tone="danger">{t('settings.checklist.hasErrors')}</Badge>}
          <Badge tone={isFlag ? 'danger' : 'neutral'}>
            {isFlag ? t('settings.field.typeFlag') : t('detail.weight', { value: criterion.weight })}
          </Badge>
        </Accordion.Trigger>
        <Button
          variant="ghost"
          size="icon"
          icon={LuTrash2}
          disabled={!canRemove}
          aria-label={t('settings.field.remove', { title })}
          onClick={onRemove}
        />
      </Accordion.Header>
      <Accordion.Content className="space-y-4 px-4 pb-5">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={t('settings.field.title')} error={errorText('title')}>
            <Input value={criterion.title} onChange={(event) => onChange({ title: event.target.value })} />
          </Field>
          <Field label={t('settings.field.section')}>
            <Select value={criterion.section} onChange={(event) => onChange({ section: event.target.value })}>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {labels.section(section.id, section.title)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('settings.field.weight')}>
            <Input
              type="number"
              min={0}
              max={MAX_WEIGHT}
              disabled={isFlag}
              value={criterion.weight}
              onChange={(event) => onChange({ weight: clampWeight(event.target.value) })}
            />
          </Field>
          <Field label={t('settings.field.type')}>
            <Select value={criterion.type} onChange={(event) => onChange(withType(criterion, event.target.value))}>
              {CRITERION_TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`settings.field.type_${type}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        {criterion.type === 'scale' && (
          <ScaleEditor steps={criterion.scale} error={errorText('scale')} onChange={(scale) => onChange({ scale })} />
        )}

        {isFlag && (
          <Field label={t('settings.field.flagTypes')} hint={t('settings.field.flagTypesHint')}>
            <Input
              key={criterion.flag_types.join()}
              defaultValue={criterion.flag_types.join(', ')}
              onBlur={(event) => onChange({ flag_types: parseList(event.target.value) })}
            />
          </Field>
        )}

        {!isFlag && (
          <div className="space-y-2">
            <Checkbox
              label={t('settings.field.naAllowed')}
              checked={criterion.na_allowed}
              onChange={(naAllowed) => onChange({ na_allowed: naAllowed, na_condition: naAllowed ? criterion.na_condition : '' })}
            />
            {criterion.na_allowed && (
              <Field label={t('settings.field.naCondition')} error={errorText('na_condition')}>
                <Input value={criterion.na_condition} onChange={(event) => onChange({ na_condition: event.target.value })} />
              </Field>
            )}
          </div>
        )}

        <Field label={t('settings.field.rule')} hint={t('settings.field.ruleHint')} error={errorText('rule')}>
          <Textarea rows={2} value={criterion.rule} onChange={(event) => onChange({ rule: event.target.value })} />
        </Field>
        <Field label={t('settings.field.guidance')} hint={t('settings.field.guidanceHint')}>
          <Textarea rows={4} value={criterion.guidance} onChange={(event) => onChange({ guidance: event.target.value })} />
        </Field>
      </Accordion.Content>
    </Accordion.Item>
  )
}
