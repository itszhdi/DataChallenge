import { useTranslation } from 'react-i18next'
import { LuMessageCircle, LuPhone } from 'react-icons/lu'
import { CHANNEL } from '../../lib/constants'
import Badge from '../ui/Badge'

export default function ChannelBadge({ channel }) {
  const { t } = useTranslation()
  return channel === CHANNEL.CALL ? (
    <Badge tone="info" icon={LuPhone}>
      {t('channel.call')}
    </Badge>
  ) : (
    <Badge icon={LuMessageCircle}>{t('channel.chat')}</Badge>
  )
}
