import { createHashRouter, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import RouteError from './components/layout/RouteError'
import { LoadingState } from './components/ui/States'
import { isChunkError, reloadForNewVersion } from './lib/chunkReload'

const NEVER = new Promise(() => {})

// Кусок кода страницы не загрузился из-за новой сборки — перезагружаемся, пока не дошло до экрана ошибки
const page = (load) => () =>
  load().then(
    (module) => ({ Component: module.default }),
    (error) => (isChunkError(error) && reloadForNewVersion() ? NEVER : Promise.reject(error)),
  )

// Hash-роутинг работает из любого пути, это нужно для HTML-компонента Dynamics 365
export const router = createHashRouter([
  {
    element: <AppLayout />,
    hydrateFallbackElement: <LoadingState />,
    children: [
      {
        // Ошибка любой страницы показывается внутри макета, а не стандартным экраном React Router
        errorElement: <RouteError />,
        children: [
          { index: true, lazy: page(() => import('./pages/OverviewPage')) },
          { path: 'dialogs', lazy: page(() => import('./pages/DialogsPage')) },
          { path: 'dialogs/:id', lazy: page(() => import('./pages/DialogDetailPage')) },
          { path: 'settings', lazy: page(() => import('./pages/SettingsPage')) },
          { path: '*', element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
])
