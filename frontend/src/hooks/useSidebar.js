import { useState } from 'react'
import { STORAGE_KEYS } from '../lib/constants'
import { useLocalStorage } from './useLocalStorage'
import { useMediaQuery } from './useMediaQuery'

// На десктопе панель остаётся в потоке и её состояние запоминается; на телефоне она выезжает поверх контента
export function useSidebar() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const [desktopOpen, setDesktopOpen] = useLocalStorage(STORAGE_KEYS.sidebar, true)
  const [mobileOpen, setMobileOpen] = useState(false)
  return {
    isMobile,
    isOpen: isMobile ? mobileOpen : desktopOpen,
    toggle: () => (isMobile ? setMobileOpen(!mobileOpen) : setDesktopOpen(!desktopOpen)),
    closeMobile: () => setMobileOpen(false),
  }
}
