import { useEffect, useState } from 'react'

const TICK_MS = 1000

// Текущее время с ежесекундным обновлением, пока активен таймер
export function useNow(isActive) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!isActive) return undefined
    const timer = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(timer)
  }, [isActive])
  return now
}
