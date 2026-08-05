import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ToastContainer from './Toast'
import ConfirmDialog from './ConfirmDialog'
import ErrorBoundary from './ErrorBoundary'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/utils/cn'
import { MenuIcon, SunIcon, MoonIcon } from '@/components/Icons'

export default function Layout() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen)
  const theme = useUIStore((s) => s.theme)
  const toggleTheme = useUIStore((s) => s.toggleTheme)

  // Initialize theme class on mount
  useEffect(() => {
    const stored = useUIStore.getState().theme
    document.documentElement.classList.toggle('light', stored === 'light')
    document.documentElement.classList.toggle('dark', stored === 'dark')
  }, [])

  return (
    <ErrorBoundary>
    <div className="min-h-screen text-surface-100">
      {/* Ambient stage — fixed radial glows + film grain (InvestIQ look).
          The wrapper above must stay transparent (no bg-*) so the negative-
          z stage shows through; body supplies the base background. */}
      <div className="stage" aria-hidden />
      <div className="grain hidden sm:block" aria-hidden />
      <Sidebar />

      {/* Mobile menu button */}
      <button
        onClick={() => setMobileSidebarOpen(true)}
        className="fixed top-4 left-4 z-20 md:hidden w-9 h-9 rounded-xl bg-surface-900/90 backdrop-blur-xl border border-surface-700/30 flex items-center justify-center text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-all duration-200"
        aria-label="Open sidebar"
      >
        <MenuIcon size={18} />
      </button>

      <main className={cn(
        'min-h-screen transition-all duration-300 ease-in-out',
        'md:ml-60',
        collapsed && 'md:ml-16',
        'pt-14 md:pt-0',
      )}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8">
          <Outlet />
        </div>
      </main>

      {/* Floating theme toggle — bottom-right corner */}
      <button
        onClick={toggleTheme}
        className="fixed bottom-6 right-6 z-50 w-11 h-11 rounded-full bg-surface-800/90 backdrop-blur-xl border border-surface-700/30 flex items-center justify-center text-surface-400 hover:text-surface-200 hover:bg-surface-700 shadow-lg hover:shadow-xl transition-all duration-200 active:scale-95"
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
      >
        {theme === 'dark' ? <SunIcon size={18} /> : <MoonIcon size={18} />}
      </button>

      {/* Global overlays */}
      <ToastContainer />
      <ConfirmDialog />
    </div>
    </ErrorBoundary>
  )
}
