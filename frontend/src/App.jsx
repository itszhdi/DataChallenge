import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import DatasetProvider from './components/layout/DatasetProvider'
import { useTheme } from './hooks/useTheme'
import { router } from './router'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

export default function App() {
  const { theme } = useTheme()
  return (
    <QueryClientProvider client={queryClient}>
      <DatasetProvider>
        <RouterProvider router={router} />
      </DatasetProvider>
      <Toaster theme={theme} position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  )
}
