import { createHashRouter, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import { LoadingState } from './components/ui/States'

const page = (load) => () => load().then((module) => ({ Component: module.default }))

// Hash-роутинг работает из любого пути, это нужно для HTML-компонента Dynamics 365
export const router = createHashRouter([
  {
    element: <AppLayout />,
    hydrateFallbackElement: <LoadingState />,
    children: [
      { index: true, lazy: page(() => import('./pages/OverviewPage')) },
      { path: 'dialogs', lazy: page(() => import('./pages/DialogsPage')) },
      { path: 'dialogs/:id', lazy: page(() => import('./pages/DialogDetailPage')) },
      { path: 'settings', lazy: page(() => import('./pages/SettingsPage')) },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
