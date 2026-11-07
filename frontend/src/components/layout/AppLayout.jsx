import { Outlet } from 'react-router-dom'
import { useSidebar } from '../../hooks/useSidebar'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

export default function AppLayout() {
  const { isMobile, isOpen, toggle, closeMobile } = useSidebar()
  return (
    <div className="min-h-screen">
      <Navbar isSidebarOpen={isOpen} onToggleSidebar={toggle} />
      <div className="flex">
        <Sidebar isMobile={isMobile} isOpen={isOpen} onCloseMobile={closeMobile} />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
