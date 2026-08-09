import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { create } from 'zustand'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { cn } from '@/utils/cn'
import {
  SearchIcon, UsersIcon, BotIcon, WorkflowIcon, BrainIcon, WrenchIcon,
  CpuIcon, FileTextIcon, KeyIcon, ArchiveIcon, GitBranchIcon, ActivityIcon,
  GlobeIcon, DashboardIcon, PlusIcon, ArrowRightIcon, LayersIcon,
} from '@/components/Icons'

// ─── Open/close state (module-level so any component can trigger it) ──
interface PaletteState {
  isOpen: boolean
  open: () => void
  close: () => void
}

export const useCommandPalette = create<PaletteState>((set) => ({
  isOpen: false,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
}))

interface CmdItem {
  id: string
  label: string
  hint?: string
  icon: React.FC<{ size?: number; className?: string }>
  action: () => void
  group: string
  keywords?: string
}

// ─── Nav destinations (grouped, industry-style) ─────────────────────
const NAV: { group: string; items: { label: string; path: string; icon: React.FC<any>; keywords?: string }[] }[] = [
  {
    group: 'Overview',
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
      { label: 'Workspaces', path: '/workspaces', icon: UsersIcon, keywords: 'project team org' },
      { label: 'Gallery', path: '/gallery', icon: GlobeIcon, keywords: 'public agents templates' },
    ],
  },
  {
    group: 'Build',
    items: [
      { label: 'Agents', path: '/agents', icon: BotIcon, keywords: 'ai assistant bot' },
      { label: 'Workflows', path: '/workflows', icon: WorkflowIcon, keywords: 'automation dag pipeline' },
      { label: 'Prompts', path: '/prompts', icon: FileTextIcon, keywords: 'template prompt registry' },
      { label: 'Tools', path: '/tools', icon: WrenchIcon, keywords: 'functions mcp webhook' },
    ],
  },
  {
    group: 'Integrate',
    items: [
      { label: 'MCP Gateway', path: '/mcp', icon: CpuIcon, keywords: 'llm chat models routing' },
      { label: 'Providers', path: '/providers', icon: GlobeIcon, keywords: 'api keys openai anthropic' },
      { label: 'API Keys', path: '/api-keys', icon: KeyIcon, keywords: 'tokens programmatic access' },
    ],
  },
  {
    group: 'Observe',
    items: [
      { label: 'Memory', path: '/memory', icon: BrainIcon, keywords: 'session context recall' },
      { label: 'Secrets', path: '/secrets', icon: KeyIcon, keywords: 'credentials vault' },
      { label: 'Artifacts', path: '/artifacts', icon: ArchiveIcon, keywords: 'files assets versions' },
      { label: 'Graphs', path: '/graphs', icon: GitBranchIcon, keywords: 'execution traces nodes' },
      { label: 'Telemetry', path: '/telemetry', icon: ActivityIcon, keywords: 'events audit logs metrics' },
    ],
  },
]

function matches(query: string, haystack: string): boolean {
  if (!query) return true
  const q = query.toLowerCase()
  const h = haystack.toLowerCase()
  // Fuzzy: every query char must appear in order
  let i = 0
  for (const ch of q) {
    i = h.indexOf(ch, i)
    if (i === -1) return false
    i++
  }
  return true
}

export default function CommandPalette() {
  const isOpen = useCommandPalette((s) => s.isOpen)
  const paletteClose = useCommandPalette((s) => s.close)
  const paletteOpen = useCommandPalette((s) => s.open)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const { setSelectedWorkspace } = useWorkspaceStore()

  // Workspaces for jump-to (fetched lazily once the palette opens)
  const { data: workspaces } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.get('/workspaces/').then((r) => r.data),
    enabled: isOpen,
    staleTime: 60_000,
  })
  const wsList: { id: string; name: string }[] = Array.isArray(workspaces) ? workspaces : []

  // ─── Keyboard: open/close ───────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        paletteOpen()
      }
      if (e.key === 'Escape') paletteClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [paletteOpen, paletteClose])

  // Reset query + scroll when opening
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [isOpen])

  const close = () => paletteClose()

  // ─── Build the item list ─────────────────────────────────
  const items = useMemo<CmdItem[]>(() => {
    const navItems: CmdItem[] = []
    for (const group of NAV) {
      for (const item of group.items) {
        const haystack = `${item.label} ${item.keywords || ''} ${group.group}`
        if (matches(query, haystack)) {
          navItems.push({
            id: `nav-${item.path}`,
            label: item.label,
            hint: group.group,
            icon: item.icon,
            group: group.group,
            keywords: haystack,
            action: () => { navigate(item.path); close() },
          })
        }
      }
    }

    const wsItems: CmdItem[] = wsList.map((ws) => ({
      id: `ws-${ws.id}`,
      label: ws.name,
      hint: 'Open workspace',
      icon: UsersIcon,
      group: 'Workspaces',
      keywords: `workspace ${ws.name}`,
      action: () => { setSelectedWorkspace(ws.id, ws.name); navigate(`/workspaces/${ws.id}`); close() },
    }))

    const quick: CmdItem[] = [
      { id: 'new-ws', label: 'New workspace', hint: 'Create', icon: PlusIcon, group: 'Actions', keywords: 'create workspace new', action: () => { navigate('/workspaces'); close() } },
      { id: 'new-agent', label: 'New agent', hint: 'Create', icon: BotIcon, group: 'Actions', keywords: 'create agent new', action: () => { navigate('/agents'); close() } },
      { id: 'new-workflow', label: 'New workflow', hint: 'Create', icon: WorkflowIcon, group: 'Actions', keywords: 'create workflow new', action: () => { navigate('/workflows'); close() } },
      { id: 'new-prompt', label: 'New prompt', hint: 'Create', icon: FileTextIcon, group: 'Actions', keywords: 'create prompt new', action: () => { navigate('/prompts'); close() } },
      { id: 'add-provider', label: 'Add provider', hint: 'Configure', icon: GlobeIcon, group: 'Actions', keywords: 'add api key provider configure', action: () => { navigate('/providers'); close() } },
      { id: 'new-tool', label: 'New tool', hint: 'Create', icon: WrenchIcon, group: 'Actions', keywords: 'create tool new', action: () => { navigate('/tools'); close() } },
    ]

    return [...navItems, ...wsItems, ...quick]
  }, [query, wsList, navigate, setSelectedWorkspace])

  // Group for display
  const groups = useMemo(() => {
    const order = ['Overview', 'Build', 'Integrate', 'Observe', 'Workspaces', 'Actions']
    const map = new Map<string, CmdItem[]>()
    for (const item of items) {
      if (!map.has(item.group)) map.set(item.group, [])
      map.get(item.group)!.push(item)
    }
    return order.filter((g) => map.has(g)).map((g) => ({ group: g, items: map.get(g)! }))
  }, [items])

  // Flattened for keyboard nav
  const flat = useMemo(() => groups.flatMap((g) => g.items), [groups])

  // Arrow key nav + scroll into view
  useEffect(() => {
    if (active >= flat.length) setActive(flat.length - 1)
  }, [flat.length, active])

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${active}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, flat.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); flat[active]?.action() }
    else if (e.key === 'Escape') close()
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-[90] flex items-start justify-center pt-[16vh] px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />

          {/* Panel */}
          <motion.div
            className="relative w-full max-w-lg glass-strong rounded-2xl overflow-hidden shadow-2xl border-white/15"
            initial={{ opacity: 0, scale: 0.97, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            role="dialog"
            aria-label="Command palette"
          >
            {/* Input */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-white/[0.07]">
              <SearchIcon size={17} className="text-surface-500 flex-shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => { setQuery(e.target.value); setActive(0) }}
                onKeyDown={onKeyDown}
                placeholder="Search pages, workspaces, actions…"
                className="flex-1 bg-transparent outline-none text-sm text-surface-100 placeholder-surface-500"
              />
              <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded-md bg-surface-800 border border-surface-700/50 text-[10px] font-mono text-surface-500">
                esc
              </kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[46vh] overflow-y-auto py-2" onMouseDown={(e) => e.preventDefault()}>
              {groups.length === 0 && (
                <div className="px-4 py-10 text-center">
                  <p className="text-sm text-surface-500">No results for “{query}”</p>
                </div>
              )}
              {groups.map((g) => (
                <div key={g.group} className="mb-1">
                  <p className="microlabel px-4 pt-2 pb-1.5" style={{ fontSize: '9px' }}>
                    {g.group}
                  </p>
                  {g.items.map((item) => {
                    const flatIdx = flat.indexOf(item)
                    return (
                      <button
                        key={item.id}
                        data-idx={flatIdx}
                        onClick={item.action}
                        onMouseEnter={() => setActive(flatIdx)}
                        className={cn(
                          'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors duration-100',
                          active === flatIdx
                            ? 'bg-primary-500/10 text-surface-100'
                            : 'text-surface-400',
                        )}
                      >
                        <span
                          className={cn(
                            'flex items-center justify-center w-7 h-7 rounded-lg border flex-shrink-0 transition-colors',
                            active === flatIdx
                              ? 'bg-primary-500/15 border-primary-500/30 text-primary-300'
                              : 'bg-surface-800/70 border-surface-700/40 text-surface-500',
                          )}
                        >
                          <item.icon size={14} />
                        </span>
                        <span className="flex-1 min-w-0">
                          <span className="block text-sm font-medium truncate">{item.label}</span>
                          {item.hint && <span className="block text-[11px] text-surface-600 truncate">{item.hint}</span>}
                        </span>
                        <ArrowRightIcon size={13} className="text-surface-600 flex-shrink-0 opacity-0 group-hover:opacity-100" />
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.07] bg-surface-900/40">
              <div className="flex items-center gap-3 text-[10px] text-surface-600 font-mono">
                <span><kbd className="text-surface-500">↑↓</kbd> navigate</span>
                <span><kbd className="text-surface-500">↵</kbd> open</span>
                <span><kbd className="text-surface-500">esc</kbd> close</span>
              </div>
              <span className="text-[10px] text-surface-600 flex items-center gap-1">
                <LayersIcon size={10} /> {flat.length} results
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Convenience: a small "⌘K" button trigger used in the sidebar/topbar.
export function CommandPaletteTrigger() {
  const paletteOpen = useCommandPalette((s) => s.open)
  return (
    <button
      onClick={paletteOpen}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 text-surface-400 hover:text-surface-200 hover:bg-surface-800/60 border border-surface-700/20 bg-surface-900/40"
    >
      <SearchIcon size={16} />
      <span className="flex-1 text-left">Search…</span>
      <kbd className="px-1.5 py-0.5 rounded-md bg-surface-800 border border-surface-700/50 text-[10px] font-mono text-surface-500">
        ⌘K
      </kbd>
    </button>
  )
}
