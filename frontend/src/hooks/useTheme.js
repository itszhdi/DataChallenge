import { useEffect, useSyncExternalStore } from 'react'
import { STORAGE_KEYS } from '../lib/constants'

const listeners = new Set()

const readTheme = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.theme)
    if (stored === 'dark' || stored === 'light') return stored
  } catch {
    // Хранилище недоступно: берём системную тему
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

let currentTheme = readTheme()

const subscribe = (listener) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

const setTheme = (theme) => {
  currentTheme = theme
  try {
    localStorage.setItem(STORAGE_KEYS.theme, theme)
  } catch {
    // Выбор останется только до перезагрузки
  }
  listeners.forEach((listener) => listener())
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, () => currentTheme)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])
  return { theme, toggleTheme: () => setTheme(theme === 'dark' ? 'light' : 'dark') }
}
