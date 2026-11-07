import { Outlet } from 'react-router-dom'
import { useSidebar } from '../../hooks/useSidebar'
import JobBanner from '../job/JobBanner'
import JobProvider from '../job/JobProvider'
import JobResultModal from '../job/JobResultModal'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

export default function AppLayout() {
  const { isMobile, isOpen, toggle, closeMobile } = useSidebar()
  return (
    <JobProvider>
      <div className="min-h-screen">
        <Navbar isSidebarOpen={isOpen} onToggleSidebar={toggle} />
        <div className="flex">
          <Sidebar isMobile={isMobile} isOpen={isOpen} onCloseMobile={closeMobile} />
          <div className="min-w-0 flex-1">
            <JobBanner />
            <main className="p-4 sm:p-6 lg:p-8">
              <Outlet />
            </main>
          </div>
        </div>
      </div>
      <JobResultModal />
    </JobProvider>
  )
}
