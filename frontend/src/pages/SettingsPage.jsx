import { useTranslation } from 'react-i18next'
import PageHeader from '../components/layout/PageHeader'

export default function SettingsPage() {
  const { t } = useTranslation()
  return <PageHeader title={t('nav.settings')} />
}
