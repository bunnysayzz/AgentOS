import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ToastContainer from './Toast'
import ConfirmDialog from './ConfirmDialog'
import ErrorBoundary from './ErrorBoundary'
import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'
import { LogoIcon, MenuIcon, SunIcon, MoonIcon, XIcon } from '@/components/Icons'

export default function Layout() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen)
  const theme = useUIStore((s) => s.theme)
  const toggleTheme = useUIStore((s) => s.toggleTheme)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [guestBannerDismissed, setGuestBannerDismissed] = useState(
    () => sessionStorage.getItem('agentos-guest-banner') === '1',
  )

  const dismissGuestBanner = () => {
    setGuestBannerDismissed(true)
    sessionStorage.setItem('agentos-guest-banner', '1')
  }

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
          {/* Guest banner — visitors can browse freely, sign-in lives inside the app */}
          {!isAuthenticated && !guestBannerDismissed && (
            <div className="mb-6 flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-primary-500/10 via-primary-600/5 to-transparent border border-primary-500/20 backdrop-blur-sm">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center flex-shrink-0 shadow-lg shadow-primary-500/20">
                <LogoIcon size={16} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-surface-100">You're browsing as a guest</p>
                <p className="text-xs text-surface-500 truncate sm:whitespace-normal">
                  Sign in to save your workspaces, agents, and data across every page.
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  to="/login"
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-lg shadow-primary-500/20"
                  style={{ color: '#141007', background: 'linear-gradient(120deg, #b8842f, #e3b862)' }}
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="px-3 py-1.5 rounded-lg bg-surface-800/80 hover:bg-surface-800 border border-surface-700/50 text-surface-200 text-xs font-medium transition-colors"
                >
                  Create account
                </Link>
                <button
                  onClick={dismissGuestBanner}
                  className="p-1.5 rounded-lg text-surface-500 hover:text-surface-200 hover:bg-surface-800/50 transition-colors"
                  aria-label="Dismiss guest banner"
                >
                  <XIcon size={14} />
                </button>
              </div>
            </div>
          )}
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
