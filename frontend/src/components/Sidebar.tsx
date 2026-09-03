import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { cn } from '@/utils/cn'
import { ActivityIcon, ArchiveIcon, BarChart3Icon, BotIcon, BrainIcon, ChevronLeftIcon, ChevronRightIcon, CpuIcon, DashboardIcon, FileTextIcon, GitBranchIcon, GlobeIcon, KeyIcon, LogInIcon, LogoIcon, LogOutIcon, ServerIcon, SettingsIcon, TrendingUpIcon, UserPlusIcon, UsersIcon, WorkflowIcon, WrenchIcon, XIcon, CheckIcon, ChevronDownIcon, WalletIcon, WebhookIcon } from '@/components/Icons'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { firebaseAuth, firebaseSignOut } from '@/services/firebase'
import { CommandPaletteTrigger } from '@/components/CommandPalette'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'

// ─── Navigation, grouped like industry tools (Overview / Build / …) ──
const NAV_SECTIONS: { label: string; items: { label: string; path: string; icon: React.FC<any> }[] }[] = [
  {
    label: 'Overview',
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
      { label: 'Workspaces', path: '/workspaces', icon: UsersIcon },
      { label: 'Gallery', path: '/gallery', icon: GlobeIcon },
    ],
  },
  {
    label: 'Build',
    items: [
      { label: 'Agents', path: '/agents', icon: BotIcon },
      { label: 'Workflows', path: '/workflows', icon: WorkflowIcon },
      { label: 'Prompts', path: '/prompts', icon: FileTextIcon },
      { label: 'Tools', path: '/tools', icon: WrenchIcon },
    ],
  },
  {
    label: 'Integrate',
    items: [
      { label: 'MCP Gateway', path: '/mcp', icon: CpuIcon },
      { label: 'Providers', path: '/providers', icon: GlobeIcon },
      { label: 'API Keys', path: '/api-keys', icon: KeyIcon },
    ],
  },
  {
    label: 'Observe',
    items: [
      { label: 'Memory', path: '/memory', icon: BrainIcon },
      { label: 'Secrets', path: '/secrets', icon: KeyIcon },
      { label: 'Artifacts', path: '/artifacts', icon: ArchiveIcon },
      { label: 'Graphs', path: '/graphs', icon: GitBranchIcon },
      { label: 'Telemetry', path: '/telemetry', icon: ActivityIcon },
      { label: 'Budget', path: '/budget', icon: WalletIcon },
      { label: 'Webhook Debugger', path: '/webhook-debugger', icon: WebhookIcon },
    ],
  },
  {
    label: 'Test & Ship',
    items: [
      { label: 'Evaluations', path: '/evaluations', icon: BarChart3Icon },
      { label: 'A/B Testing', path: '/ab-testing', icon: TrendingUpIcon },
      { label: 'Infrastructure', path: '/iac', icon: ServerIcon },
    ],
  },
]

// Workspace switcher embedded in the sidebar (collapsed → chevron only)
function SidebarWorkspaceSwitcher({ collapsed }: { collapsed: boolean }) {
  const [open, setOpen] = useState(false)
  const { selectedWorkspaceId, selectedWorkspaceName, setSelectedWorkspace } = useWorkspaceStore()
  const { data: workspaces } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.get('/workspaces/').then((r) => r.data),
  })
  const list: { id: string; name: string }[] = Array.isArray(workspaces) ? workspaces : []
  if (list.length === 0) return null

  return (
    <div className="relative px-2">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition-all duration-200',
          'bg-surface-900/60 border border-surface-700/30 hover:border-surface-600/60 text-surface-200',
          collapsed && 'justify-center px-1',
        )}
        title={selectedWorkspaceName || 'Select workspace'}
      >
        <span className={cn(
          'flex items-center justify-center w-5 h-5 rounded-md text-[10px] font-bold flex-shrink-0',
          'bg-primary-500/15 text-primary-400 border border-primary-500/25',
        )}>
          {(selectedWorkspaceName || 'W').slice(0, 1).toUpperCase()}
        </span>
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate text-[13px]">
              {selectedWorkspaceName || 'Select workspace'}
            </span>
            <ChevronDownIcon size={13} className="text-surface-500 flex-shrink-0" />
          </>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute left-2 right-2 top-full mt-1 z-20 glass-panel p-1 shadow-xl max-h-60 overflow-y-auto">
            {list.map((ws) => (
              <button
                key={ws.id}
                onClick={() => {
                  setSelectedWorkspace(ws.id, ws.name)
                  setOpen(false)
                }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-150',
                  selectedWorkspaceId === ws.id
                    ? 'bg-primary-500/10 text-primary-400'
                    : 'text-surface-300 hover:bg-surface-800',
                )}
              >
                <span className="flex-1 text-left truncate">{ws.name}</span>
                {selectedWorkspaceId === ws.id && <CheckIcon size={13} className="flex-shrink-0" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default function Sidebar() {
  const { sidebarCollapsed: collapsed, toggleSidebar, mobileSidebarOpen, setMobileSidebarOpen } = useUIStore()
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const clearSelectedWorkspace = useWorkspaceStore((s) => s.clearSelectedWorkspace)
  const location = useLocation()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    try { await firebaseSignOut(firebaseAuth) } catch { /* ignore */ }
    clearAuth()
    clearSelectedWorkspace()
    localStorage.removeItem('agentos-auth')
    localStorage.removeItem('agentos-workspace')
    navigate('/')
  }

  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [location.pathname, setMobileSidebarOpen])

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
          // Native-app feel: a spring-like curve instead of linear ease
          'transition-[width,transform] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]',
          'md:translate-x-0',
          mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full',
          collapsed ? 'w-60 md:w-16' : 'w-60',
        )}
      >
        {/* Logo */}
        <div className={cn('flex items-center h-16 border-b border-white/[0.05] flex-shrink-0', collapsed ? 'justify-center' : 'px-5')}>
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#15132a] to-[#0a0818] border border-primary-500/40 flex items-center justify-center flex-shrink-0 shadow-lg shadow-primary-500/20">
              <LogoIcon size={17} />
            </div>
            {!collapsed && (
              <div className="min-w-0 leading-tight">
                <span className="text-sm font-semibold tracking-tight text-surface-100">
                  Agent<span className="text-primary-400">OS</span>
                </span>
                <span className="microlabel block mt-0.5" style={{ fontSize: '8.5px', letterSpacing: '0.18em' }}>
                  studio
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Search / Cmd+K */}
        <div className={cn('pt-3 flex-shrink-0', collapsed ? 'px-2' : 'px-3')}>
          {!collapsed && <CommandPaletteTrigger />}
        </div>

        {/* Workspace switcher */}
        <div className={cn('mt-2 flex-shrink-0', collapsed && 'px-2')}>
          <SidebarWorkspaceSwitcher collapsed={collapsed} />
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label}>
              {!collapsed && (
                <p className="microlabel px-3 mb-1.5" style={{ fontSize: '9px', letterSpacing: '0.16em' }}>
                  {section.label}
                </p>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center gap-3 px-3 py-2 rounded-xl text-[13px] font-medium transition-all duration-200',
                        isActive
                          ? 'bg-gradient-to-r from-primary-500/15 to-primary-500/[0.03] text-primary-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]'
                          : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800/60 active:scale-[0.98]',
                        collapsed && 'justify-center px-2',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {/* Active accent bar */}
                        {isActive && !collapsed && (
                          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full bg-gradient-to-b from-primary-400 to-primary-600 shadow-[0_0_8px_rgba(139,92,246,0.6)]" />
                        )}
                        <item.icon
                          className={cn(
                            'w-[18px] h-[18px] flex-shrink-0 transition-colors',
                            isActive && 'text-primary-400',
                          )}
                          size={18}
                        />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className={cn('border-t border-surface-700/30 py-3 flex-shrink-0', collapsed ? 'px-2' : 'px-3')}>
          {isAuthenticated ? (
            <>
              <button
                onClick={() => navigate('/profile')}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 mb-1',
                  'text-surface-400 hover:text-surface-200 hover:bg-surface-800/50',
                  collapsed && 'justify-center px-2',
                )}
              >
                <SettingsIcon size={18} />
                {!collapsed && <span>Settings</span>}
              </button>

              <button
                onClick={handleSignOut}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200',
                  'text-surface-400 hover:text-red-400 hover:bg-red-500/10',
                  collapsed && 'justify-center px-2',
                )}
              >
                <LogOutIcon size={18} />
                {!collapsed && <span>Sign out</span>}
              </button>
            </>
          ) : (
            <div className={cn('space-y-1.5', collapsed && 'flex flex-col items-center')}>
              {!collapsed && (
                <div className="px-3 py-2.5 rounded-xl bg-primary-500/5 border border-primary-500/15">
                  <p className="text-xs font-semibold text-primary-400">Guest mode</p>
                  <p className="text-[11px] text-surface-500 mt-0.5 leading-snug">
                    Explore freely. Sign in to save your work.
                  </p>
                </div>
              )}
              <Link
                to="/login"
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[13px] font-semibold shadow-lg shadow-primary-500/20 transition-all duration-200 hover:shadow-primary-500/30"
                style={{ color: '#fff', background: 'linear-gradient(120deg, #7c3aed, #a78bfa)' }}
              >
                <LogInIcon size={16} />
                {!collapsed && <span>Sign in</span>}
              </Link>
              <Link
                to="/register"
                className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[13px] font-medium bg-surface-800/60 hover:bg-surface-800 border border-surface-700/40 text-surface-200 transition-all duration-200"
              >
                <UserPlusIcon size={16} />
                {!collapsed && <span>Create account</span>}
              </Link>
            </div>
          )}

          <button
            onClick={toggleSidebar}
            className="hidden md:flex w-full items-center justify-center gap-2 px-3 py-2 rounded-xl text-surface-500 hover:text-surface-300 hover:bg-surface-800/50 transition-all duration-200 text-[13px] active:scale-[0.97]"
          >
            {collapsed ? <ChevronRightIcon size={16} /> : <><ChevronLeftIcon size={16} /> Collapse</>}
          </button>
          <button
            onClick={() => setMobileSidebarOpen(false)}
            className="flex md:hidden w-full items-center justify-center gap-2 px-3 py-2 rounded-xl text-surface-500 hover:text-surface-300 hover:bg-surface-800/50 transition-all duration-200 text-[13px]"
          >
            <XIcon size={16} /> Close
          </button>
        </div>
      </aside>
    </>
  )
}
