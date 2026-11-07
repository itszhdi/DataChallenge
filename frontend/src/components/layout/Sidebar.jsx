import * as Dialog from '@radix-ui/react-dialog'
import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuChartColumn, LuMessagesSquare, LuX } from 'react-icons/lu'
import { NavLink } from 'react-router-dom'
import Button from '../ui/Button'

const LINKS = [
  { to: '/', end: true, labelKey: 'nav.overview', icon: LuChartColumn },
  { to: '/dialogs', labelKey: 'nav.dialogs', icon: LuMessagesSquare },
]

function SidebarLinks({ onNavigate }) {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('nav.main')} className="flex flex-col gap-1">
      {LINKS.map(({ to, end, labelKey, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium whitespace-nowrap',
              isActive ? 'bg-brand-soft text-brand-text' : 'text-ink-muted hover:bg-surface-muted hover:text-ink',
            )
          }
        >
          <Icon className="size-5" />
          {t(labelKey)}
        </NavLink>
      ))}
    </nav>
  )
}

function MobileSidebar({ isOpen, onClose }) {
  const { t } = useTranslation()
  return (
    <Dialog.Root open={isOpen} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content
          aria-describedby={undefined}
          className="glass sidebar-drawer fixed inset-y-0 left-0 z-50 w-64 max-w-[80vw] border-r border-line p-3 text-ink"
        >
          <div className="mb-2 flex items-center justify-between">
            <Dialog.Title className="px-3 text-sm font-semibold">{t('nav.main')}</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" icon={LuX} aria-label={t('nav.closeMenu')} />
            </Dialog.Close>
          </div>
          <SidebarLinks onNavigate={onClose} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export default function Sidebar({ isMobile, isOpen, onCloseMobile }) {
  if (isMobile) return <MobileSidebar isOpen={isOpen} onClose={onCloseMobile} />
  return (
    <aside
      inert={!isOpen}
      className={clsx(
        'glass sticky top-16 h-[calc(100vh-4rem)] shrink-0 overflow-hidden border-line transition-[width] duration-200',
        isOpen ? 'w-56 border-r' : 'w-0',
      )}
    >
      <div className="w-56 p-3">
        <SidebarLinks />
      </div>
    </aside>
  )
}
