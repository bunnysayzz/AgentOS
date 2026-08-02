import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { cn } from '@/utils/cn'
import { ActivityIcon, ArchiveIcon, BotIcon, BrainIcon, ChevronLeftIcon, ChevronRightIcon, CpuIcon, DashboardIcon, FileTextIcon, GitBranchIcon, KeyIcon, LogoIcon, LogOutIcon, SettingsIcon, UsersIcon, WorkflowIcon, WrenchIcon, XIcon } from '@/components/Icons'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { firebaseAuth, firebaseSignOut } from '@/services/firebase'

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
  { label: 'Workspaces', path: '/workspaces', icon: UsersIcon },
  { label: 'Agents', path: '/agents', icon: BotIcon },
  { label: 'Workflows', path: '/workflows', icon: WorkflowIcon },
  { label: 'Memory', path: '/memory', icon: BrainIcon },
  { label: 'Tools', path: '/tools', icon: WrenchIcon },
  { label: 'MCP Gateway', path: '/mcp', icon: CpuIcon },
  { label: 'Prompts', path: '/prompts', icon: FileTextIcon },
  { label: 'Secrets', path: '/secrets', icon: KeyIcon },
  { label: 'Artifacts', path: '/artifacts', icon: ArchiveIcon },
  { label: 'Graphs', path: '/graphs', icon: GitBranchIcon },
  { label: 'Telemetry', path: '/telemetry', icon: ActivityIcon },
  { label: 'Providers', path: '/providers', icon: KeyIcon },
]

export default function Sidebar() {
  const { sidebarCollapsed: collapsed, toggleSidebar, mobileSidebarOpen, setMobileSidebarOpen } = useUIStore()
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const location = useLocation()
  const navigate = useNavigate()

  // Close mobile sidebar on navigation
  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [location.pathname, setMobileSidebarOpen])

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (mobileSidebarOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [mobileSidebarOpen])

  return (
    <>
      {/* Mobile backdrop */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 h-full z-40 flex flex-col',
          'bg-surface-900/95 backdrop-blur-xl border-r border-surface-700/30',
          'transition-all duration-300 ease-in-out',
          // Desktop: normal sidebar behavior
          'md:translate-x-0',
          // Mobile: slide in/out from left
          mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full',
          collapsed ? 'w-60 md:w-16' : 'w-60',
        )}
      >
      {/* Logo */}
      <div className={cn('flex items-center h-16 border-b border-surface-700/30', collapsed ? 'justify-center' : 'px-5')}>
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center flex-shrink-0 shadow-lg shadow-primary-500/20">
            <LogoIcon size={16} className="text-white" />
          </div>
          {!collapsed && (
            <span className="text-sm font-bold bg-gradient-to-r from-primary-400 to-primary-200 bg-clip-text text-transparent truncate">
              AgentOS
            </span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800/50 border border-transparent',
                collapsed && 'justify-center px-2',
              )
            }
          >
            <item.icon className="w-[18px] h-[18px] flex-shrink-0" size={18} />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className={cn('border-t border-surface-700/30 py-3', collapsed ? 'px-2' : 'px-3')}>
        {/* Profile link */}
        <button
          onClick={() => navigate('/profile')}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 mb-1',
            'text-surface-400 hover:text-surface-200 hover:bg-surface-800/50',
            collapsed && 'justify-center px-2',
          )}
        >
          <SettingsIcon size={18} />
          {!collapsed && <span>Settings</span>}
        </button>

        {/* Desktop collapse button */}
        <button
          onClick={toggleSidebar}
          className="hidden md:flex w-full items-center justify-center gap-2 px-3 py-2 rounded-xl text-surface-500 hover:text-surface-300 hover:bg-surface-800/50 transition-all duration-200 text-sm"
        >
          {collapsed ? <ChevronRightIcon size={16} /> : <><ChevronLeftIcon size={16} /> Collapse</>}
        </button>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileSidebarOpen(false)}
          className="flex md:hidden w-full items-center justify-center gap-2 px-3 py-2 rounded-xl text-surface-500 hover:text-surface-300 hover:bg-surface-800/50 transition-all duration-200 text-sm"
        >
          <XIcon size={16} /> Close
        </button>
        <button
          onClick={async () => {
            try { await firebaseSignOut(firebaseAuth) } catch { /* ignore */ }
            clearAuth()
            localStorage.clear()
            navigate('/login')
          }}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
            'text-surface-400 hover:text-red-400 hover:bg-red-500/10',
            collapsed && 'justify-center px-2',
          )}
        >
          <LogOutIcon size={18} />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
    </>
  )
}
