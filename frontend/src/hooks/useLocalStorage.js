import { useCallback, useState } from 'react'

const read = (key, fallback) => {
  try {
    const stored = localStorage.getItem(key)
    return stored === null ? fallback : JSON.parse(stored)
  } catch {
    return fallback
  }
}

export function useLocalStorage(key, fallback) {
  const [value, setValue] = useState(() => read(key, fallback))
  const update = useCallback(
    (next) => {
      setValue(next)
      try {
        localStorage.setItem(key, JSON.stringify(next))
      } catch {
        // Хранилище недоступно: значение остаётся в памяти до перезагрузки
      }
    },
    [key],
  )
  return [value, update]
}
