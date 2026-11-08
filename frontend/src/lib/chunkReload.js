// Страницы грузятся отдельными кусками кода. После пересборки фронта открытая вкладка ссылается
// на куски, которых уже нет на сервере: одна перезагрузка подтягивает новую версию
const RELOAD_KEY = 'cqa-chunk-reload-at'
const RELOAD_GUARD_MS = 10000
const CHUNK_ERROR = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS/i

export const isChunkError = (error) => CHUNK_ERROR.test(String(error?.message ?? error))

// true — перезагрузка запущена; false — уже перезагружались недавно, ошибку нужно показать
export function reloadForNewVersion() {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY))
    if (last && Date.now() - last < RELOAD_GUARD_MS) return false
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
  } catch {
    return false
  }
  window.location.reload()
  return true
}
