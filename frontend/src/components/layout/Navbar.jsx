import { useTranslation } from 'react-i18next'
import { LuMenu, LuMoon, LuSettings, LuSun } from 'react-icons/lu'
import { Link, NavLink } from 'react-router-dom'
import clsx from 'clsx'
import logo from '../../assets/logo.png'
import { useTheme } from '../../hooks/useTheme'
import { UI_LANGUAGES } from '../../i18n'

const ICON_BUTTON = 'flex size-9 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-surface-muted hover:text-ink'

function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  return (
    <div role="group" aria-label={t('nav.language')} className="flex shrink-0 gap-0.5 rounded-lg border border-line p-1">
      {UI_LANGUAGES.map(({ code, label }) => (
        <button
          key={code}
          type="button"
          aria-pressed={i18n.resolvedLanguage === code}
          onClick={() => i18n.changeLanguage(code)}
          className={clsx(
            'rounded-md px-2 py-1 text-xs font-semibold sm:px-3',
            i18n.resolvedLanguage === code ? 'bg-brand text-on-brand' : 'text-ink-muted hover:text-ink',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export default function Navbar({ isSidebarOpen, onToggleSidebar }) {
  const { t } = useTranslation()
  const { theme, toggleTheme } = useTheme()
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-2 border-b border-line bg-surface px-3 sm:gap-5 sm:px-8">
      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-5">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-expanded={isSidebarOpen}
          aria-label={t(isSidebarOpen ? 'nav.closeMenu' : 'nav.openMenu')}
          className={ICON_BUTTON}
        >
          <LuMenu className="size-5" />
        </button>
        <Link to="/" className="min-w-0">
          <img src={logo} alt="Freedom" className="h-8 w-auto max-w-full object-contain object-left" />
        </Link>
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-5">
        <LanguageSwitcher />
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={t(theme === 'dark' ? 'nav.lightTheme' : 'nav.darkTheme')}
          className={ICON_BUTTON}
        >
          {theme === 'dark' ? <LuSun className="size-5" /> : <LuMoon className="size-5" />}
        </button>
        <NavLink to="/settings" aria-label={t('nav.settings')} className={ICON_BUTTON}>
          <LuSettings className="size-5" />
        </NavLink>
      </div>
    </header>
  )
}
