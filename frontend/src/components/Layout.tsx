import { Suspense, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import Sidebar from './Sidebar'
import ToastContainer from './Toast'
import ConfirmDialog from './ConfirmDialog'
import ErrorBoundary from './ErrorBoundary'
import CommandPalette from './CommandPalette'
import { useUIStore } from '@/stores/uiStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import api from '@/services/api'
import { cn } from '@/utils/cn'
import { MenuIcon, SunIcon, MoonIcon } from '@/components/Icons'

function PageSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 w-48 bg-surface-800/60 rounded-lg" />
      <div className="h-4 w-72 bg-surface-800/40 rounded-md" />
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-surface-800/40 rounded-xl border border-surface-700/20" />
        ))}
      </div>
    </div>
  )
}

export default function Layout() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen)
  const theme = useUIStore((s) => s.theme)
  const toggleTheme = useUIStore((s) => s.toggleTheme)
  const location = useLocation()
  const { selectedWorkspaceId, setSelectedWorkspace } = useWorkspaceStore()

  // Auto-select a workspace as soon as the list is known: the first one if
  // nothing is chosen yet, or the persisted one if it still exists (a stale
  // id from another user or a deleted workspace falls back to the first).
  const { data: workspaces } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.get('/workspaces/').then((r) => r.data),
    retry: 1,
  })

  useEffect(() => {
    const list: { id: string; name: string }[] = Array.isArray(workspaces) ? workspaces : []
    if (list.length === 0) return
    const stillExists = list.some((ws) => ws.id === selectedWorkspaceId)
    if (!selectedWorkspaceId || !stillExists) {
      setSelectedWorkspace(list[0].id, list[0].name)
    }
  }, [workspaces, selectedWorkspaceId, setSelectedWorkspace])

  // Initialize theme class on mount
  useEffect(() => {
    const stored = useUIStore.getState().theme
    document.documentElement.classList.toggle('light', stored === 'light')
    document.documentElement.classList.toggle('dark', stored === 'dark')
  }, [])

  // Scroll to top on route change
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }, [location.pathname])

  return (
    <ErrorBoundary>
    <div className="min-h-screen text-surface-100">
      {/* Ambient stage — fixed radial glows + film grain (AgentOS look).
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
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8">
          {/* Page transitions — fade + subtle rise on every route change */}
          <AnimatePresence initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            >
              <Suspense fallback={<PageSkeleton />}>
                <Outlet />
              </Suspense>
            </motion.div>
          </AnimatePresence>
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
      <CommandPalette />
    </div>
    </ErrorBoundary>
  )
}
