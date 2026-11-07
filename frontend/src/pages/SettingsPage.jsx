import * as Tabs from '@radix-ui/react-tabs'
import { useTranslation } from 'react-i18next'
import { LuListChecks, LuPlugZap, LuTimer } from 'react-icons/lu'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../components/layout/PageHeader'
import ChecklistTab from '../components/settings/checklist/ChecklistTab'
import IntegrationSettings from '../components/settings/IntegrationSettings'
import QueueSettings from '../components/settings/QueueSettings'

const TABS = [
  { id: 'checklist', labelKey: 'settings.tabs.checklist', icon: LuListChecks, Content: ChecklistTab },
  { id: 'queue', labelKey: 'settings.tabs.queue', icon: LuTimer, Content: QueueSettings },
  { id: 'integration', labelKey: 'settings.tabs.integration', icon: LuPlugZap, Content: IntegrationSettings },
]

export default function SettingsPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const activeTab = TABS.some((tab) => tab.id === requested) ? requested : TABS[0].id

  return (
    <>
      <PageHeader title={t('nav.settings')} />
      <Tabs.Root value={activeTab} onValueChange={(tab) => setSearchParams({ tab }, { replace: true })}>
        <Tabs.List className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
          {TABS.map(({ id, labelKey, icon: Icon }) => (
            <Tabs.Trigger
              key={id}
              value={id}
              className="-mb-px flex shrink-0 items-center gap-2 border-b-2 border-transparent px-4 py-2.5 text-sm font-medium text-ink-muted hover:text-ink data-[state=active]:border-brand data-[state=active]:text-brand-text"
            >
              <Icon className="size-4" />
              {t(labelKey)}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {TABS.map(({ id, Content }) => (
          <Tabs.Content key={id} value={id}>
            <Content />
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </>
  )
}
