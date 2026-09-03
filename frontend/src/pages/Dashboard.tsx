import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ActivityIcon, ArchiveIcon, ArrowRightIcon, BotIcon, BrainIcon, CheckCircleIcon,
  CheckIcon, CpuIcon, FileTextIcon, GlobeIcon, KeyIcon, LogInIcon, LogoIcon,
  RocketIcon, SparklesIcon, UsersIcon, WorkflowIcon, WrenchIcon, DollarSignIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { cn } from '@/utils/cn'

const QUICK_ACTIONS = [
  { label: 'New Workspace', icon: UsersIcon, color: 'text-primary-400', path: '/workspaces' },
  { label: 'New Agent', icon: BotIcon, color: 'text-emerald-400', path: '/agents' },
  { label: 'New Workflow', icon: WorkflowIcon, color: 'text-violet-400', path: '/workflows' },
  { label: 'New Prompt', icon: FileTextIcon, color: 'text-amber-400', path: '/prompts' },
  { label: 'Add Provider', icon: GlobeIcon, color: 'text-sky-400', path: '/providers' },
  { label: 'New Tool', icon: WrenchIcon, color: 'text-rose-400', path: '/tools' },
]

const DOMAIN_LINKS = [
  { label: 'MCP Gateway', icon: CpuIcon, path: '/mcp', desc: 'LLM model routing & chat', color: 'text-sky-400' },
  { label: 'Prompt Registry', icon: FileTextIcon, path: '/prompts', desc: 'Versioned prompt templates', color: 'text-amber-400' },
  { label: 'Secrets Manager', icon: KeyIcon, path: '/secrets', desc: 'Encrypted credential storage', color: 'text-rose-400' },
  { label: 'Artifact Store', icon: ArchiveIcon, path: '/artifacts', desc: 'Versioned asset tracking', color: 'text-indigo-400' },
  { label: 'Telemetry', icon: ActivityIcon, path: '/telemetry', desc: 'Events, audit logs & stats', color: 'text-emerald-400' },
  { label: 'API Keys', icon: KeyIcon, path: '/api-keys', desc: 'Programmatic access management', color: 'text-amber-400' },
  { label: 'Providers', icon: GlobeIcon, path: '/providers', desc: 'AI provider configuration', color: 'text-sky-400' },
  { label: 'Memory', icon: BrainIcon, path: '/memory', desc: 'Conversation & session memory', color: 'text-pink-400' },
]

// One stable skeleton while stats load — the dashboard never flashes a
// half-built grid that later swaps to a different layout.
function DashboardSkeleton() {
  return (
    <div className="space-y-8" aria-busy="true">
      <div className="h-24 sm:h-28 rounded-3xl bg-surface-800/40 border border-surface-700/20 animate-pulse" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 rounded-2xl bg-surface-800/40 border border-surface-700/20 animate-pulse" />
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 rounded-2xl bg-surface-800/40 border border-surface-700/20 animate-pulse" />
        ))}
      </div>
      <div className="h-40 rounded-2xl bg-surface-800/40 border border-surface-700/20 animate-pulse" />
    </div>
  )
}

// How-it-works pipeline shown to guests in the hero
const PIPELINE = [
  { label: 'Prompt', icon: FileTextIcon, color: 'text-amber-400' },
  { label: 'Agent', icon: BotIcon, color: 'text-primary-400' },
  { label: 'Tools', icon: WrenchIcon, color: 'text-sky-400' },
  { label: 'Output', icon: CheckCircleIcon, color: 'text-emerald-400' },
]

const todayLong = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  // Single source of truth for the active workspace is the persisted store
  // shared with the Sidebar — never a second local copy.
  const selectedWorkspaceId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const setSelectedWorkspace = useWorkspaceStore((s) => s.setSelectedWorkspace)

  // One-time welcome: snapshot the flag at mount (fresh login), then clear it
  // so navigating away and back — or a refresh — shows the data-first view.
  const [showWelcome] = useState(
    () => useAuthStore.getState().justSignedIn && useAuthStore.getState().isAuthenticated,
  )
  useEffect(() => {
    if (showWelcome) useAuthStore.getState().acknowledgeWelcome()
  }, [showWelcome])

  // One-click demo workspace for first-run users.
  const { mutate: seedDemo, isPending: seeding } = useMutation({
    mutationFn: () => api.post('/demo/seed').then((r) => r.data),
    onSuccess: (data: { id: string; name: string }) => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      for (const key of ['agents', 'workflows', 'prompts', 'tools', 'memory', 'secrets', 'artifacts']) {
        queryClient.invalidateQueries({ queryKey: [key, data.id] })
        queryClient.invalidateQueries({ queryKey: [key] })
      }
      setSelectedWorkspace(data.id, data.name)
      navigate(`/workspaces/${data.id}`)
    },
  })

  // ─── Dashboard stats — ONE aggregate endpoint ─────────────────────
  const globalStatsQuery = useQuery({
    queryKey: ['dashboard-stats', selectedWorkspaceId],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/stats', {
        params: selectedWorkspaceId ? { workspace_id: selectedWorkspaceId, days: 7 } : { days: 7 },
      })
      const d = data || {}
      const workspaces: { id: string; name: string }[] = Array.isArray(d.workspaces) ? d.workspaces : []
      // The server returns snake_case keys; normalize the workspace tallies
      // to camelCase so the cards below can read them directly.
      const rawWs = d.workspace || null
      const ws = rawWs
        ? {
            agentCount: rawWs.agent_count ?? 0,
            workflowCount: rawWs.workflow_count ?? 0,
            promptCount: rawWs.prompt_count ?? 0,
            toolCount: rawWs.tool_count ?? 0,
            secretCount: rawWs.secret_count ?? 0,
            artifactCount: rawWs.artifact_count ?? 0,
            telemetryEvents: rawWs.telemetry_events ?? 0,
            telemetryErrors: rawWs.telemetry_errors ?? 0,
          }
        : null
      return {
        workspaces,
        workspaceCount: d.workspace_count ?? 0,
        modelCount: d.model_count ?? 0,
        callCount: d.call_count ?? 0,
        totalTokens: d.total_tokens ?? 0,
        totalCost: d.total_cost_usd ?? 0,
        keyCount: d.key_count ?? 0,
        configuredProviders: d.configured_providers ?? 0,
        firstWs: d.first_ws ?? (workspaces.length > 0 ? workspaces[0].id : null),
        ws,
      }
    },
    retry: 1,
    staleTime: 30_000,
  })

  const stats = globalStatsQuery.data

  // If nothing is selected yet (fresh login, direct deep link) but the user
  // has workspaces, adopt the first one so dashboard + sidebar agree.
  useEffect(() => {
    if (isAuthenticated && !selectedWorkspaceId && stats?.workspaceCount && stats.workspaces?.length) {
      const first = stats.workspaces[0]
      setSelectedWorkspace(first.id, first.name)
    }
  }, [stats, isAuthenticated, selectedWorkspaceId, setSelectedWorkspace])

  // One layout while loading — no swap, no flash.
  if (!stats) {
    return <DashboardSkeleton />
  }

  const wsStats = stats.ws
  const wsId = selectedWorkspaceId || stats.firstWs || ''
  const isLoading = globalStatsQuery.isLoading

  // ─── Onboarding state ─────────────────────────────────────────────
  const isNewUser = isAuthenticated && !isLoading && stats.workspaceCount === 0
  const showGettingStarted = !isAuthenticated || isNewUser
  const established = isAuthenticated && !isNewUser

  const checklistSteps = [
    {
      key: 'workspace', label: 'Create a workspace',
      desc: 'Your isolated home for agents, workflows & data',
      icon: UsersIcon, color: 'text-primary-400', path: '/workspaces',
      done: stats.workspaceCount > 0,
    },
    {
      key: 'provider', label: 'Connect an AI provider',
      desc: 'Add OpenAI, Anthropic or Gemini keys',
      icon: GlobeIcon, color: 'text-sky-400', path: '/providers',
      done: stats.configuredProviders > 0,
    },
    {
      key: 'agent', label: 'Build your first agent',
      desc: 'Give it a system prompt, tools & memory',
      icon: BotIcon, color: 'text-emerald-400', path: '/agents',
      done: (wsStats?.agentCount ?? 0) > 0,
    },
    {
      key: 'workflow', label: 'Run your first workflow',
      desc: 'Chain steps & approvals into automations',
      icon: WorkflowIcon, color: 'text-violet-400', path: '/workflows',
      done: (wsStats?.workflowCount ?? 0) > 0,
    },
  ]
  const stepsDone = checklistSteps.filter((s) => s.done).length

  // ─── Stat cards (established users with data) ─────────────────────
  const resourceCards = [
    {
      label: 'Workspaces', desc: 'Where your work lives', icon: UsersIcon,
      color: 'from-primary-500 to-primary-600', value: stats.workspaceCount,
      path: '/workspaces', show: true,
    },
    {
      label: 'Agents', desc: 'AI agents in this workspace', icon: BotIcon,
      color: 'from-emerald-500 to-emerald-600', value: wsStats?.agentCount ?? 0,
      path: '/agents', show: !!wsId,
    },
    {
      label: 'Workflows', desc: 'Automations & approvals', icon: WorkflowIcon,
      color: 'from-violet-500 to-violet-600', value: wsStats?.workflowCount ?? 0,
      path: '/workflows', show: !!wsId,
    },
    {
      label: 'Prompts', desc: 'Versioned prompt registry', icon: FileTextIcon,
      color: 'from-amber-500 to-amber-600', value: wsStats?.promptCount ?? 0,
      path: '/prompts', show: !!wsId,
    },
    {
      label: 'Tools', desc: 'Functions, MCP & webhooks', icon: WrenchIcon,
      color: 'from-rose-500 to-rose-600', value: wsStats?.toolCount ?? 0,
      path: '/tools', show: !!wsId,
    },
    {
      label: 'Secrets', desc: 'Encrypted credentials', icon: KeyIcon,
      color: 'from-cyan-500 to-cyan-600', value: wsStats?.secretCount ?? 0,
      path: '/secrets', show: !!wsId,
    },
    {
      label: 'Artifacts', desc: 'Versioned files & assets', icon: ArchiveIcon,
      color: 'from-indigo-500 to-indigo-600', value: wsStats?.artifactCount ?? 0,
      path: '/artifacts', show: !!wsId,
    },
  ].filter((c) => c.show)

  const platformCards = [
    {
      label: 'LLM Calls', icon: ActivityIcon, color: 'text-sky-400',
      value: stats.callCount, sub: 'in the last 7 days',
    },
    {
      label: 'Tokens Processed', icon: CpuIcon, color: 'text-amber-400',
      value: stats.totalTokens, sub: '7-day total',
    },
    {
      label: 'Configured Providers', icon: GlobeIcon, color: 'text-emerald-400',
      value: stats.configuredProviders, sub: `${stats.modelCount} models available`,
    },
    {
      label: 'Total Spend', icon: DollarSignIcon, color: 'text-rose-400',
      value: stats.totalCost > 0 ? `$${stats.totalCost.toFixed(6)}` : '$0', sub: '7-day total',
    },
  ]

  const firstName = user?.fullName ? user.fullName.split(' ')[0] : ''

  return (
    <div className="space-y-8">
      {/* ── One-time welcome — only right after a fresh login ─────── */}
      {isAuthenticated && showWelcome && (
        <motion.div
          className="relative overflow-hidden rounded-3xl border border-primary-500/20 bg-gradient-to-br from-primary-500/[0.12] via-surface-900/60 to-transparent p-6 sm:p-8"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.div
            className="absolute -top-24 -right-16 w-72 h-72 rounded-full bg-primary-500/15 blur-3xl pointer-events-none"
            animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.8, 0.5] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            aria-hidden
          />
          <div className="relative flex flex-col sm:flex-row sm:items-center gap-6">
            <div className="flex items-center gap-4 min-w-0 flex-1">
              <motion.div
                className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg shadow-primary-500/30 flex-shrink-0"
                initial={{ scale: 0.8, rotate: -6 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ delay: 0.1, type: 'spring', stiffness: 260, damping: 18 }}
              >
                <LogoIcon size={24} className="text-white" />
              </motion.div>
              <div className="min-w-0">
                <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-surface-100">
                  Welcome back{firstName ? `, ${firstName}` : ''}
                </h1>
                <p className="text-surface-400 mt-1 text-sm">
                  {stats.workspaceCount > 0
                    ? `You have ${stats.workspaceCount} workspace${stats.workspaceCount !== 1 ? 's' : ''} and ${stats.configuredProviders} provider${stats.configuredProviders !== 1 ? 's' : ''} ready. Pick up where you left off.`
                    : 'Let\'s set up your studio — it takes about a minute.'}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
              {stats.workspaceCount > 0 ? (
                <Link
                  to={`/workspaces/${stats.firstWs}`}
                  className="btn-primary inline-flex items-center gap-2"
                >
                  Open workspace
                  <ArrowRightIcon size={15} />
                </Link>
              ) : (
                <button onClick={() => seedDemo()} disabled={seeding} className="btn-primary inline-flex items-center gap-2">
                  {seeding ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <RocketIcon size={15} />
                  )}
                  {seeding ? 'Loading…' : 'Load demo workspace'}
                </button>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Guest hero — marketing surface, shown to visitors ─────── */}
      {!isAuthenticated && (
        <motion.div
          className="relative overflow-hidden rounded-3xl border border-white/[0.06] bg-gradient-to-br from-white/[0.04] to-transparent p-6 sm:p-10"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.div
            className="absolute -top-24 -right-16 w-72 h-72 rounded-full bg-primary-500/10 blur-3xl pointer-events-none"
            animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.8, 0.5] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            aria-hidden
          />
          <motion.div
            className="absolute -bottom-32 -left-20 w-96 h-96 rounded-full bg-info/10 blur-3xl pointer-events-none"
            animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.7, 0.4] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
            aria-hidden
          />
          <div className="relative flex flex-col lg:flex-row lg:items-center gap-8">
            <div className="flex-1 min-w-0">
              <motion.div className="flex items-center gap-3 mb-4" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2, duration: 0.4 }}>
                <motion.div
                  className="w-11 h-11 rounded-2xl bg-gradient-to-br from-[#16151a] to-[#08080b] border border-primary-600/40 flex items-center justify-center shadow-lg shadow-primary-500/25 flex-shrink-0"
                  whileHover={{ scale: 1.05, rotate: 5 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                >
                  <LogoIcon size={22} />
                </motion.div>
                <p className="microlabel">agent orchestration studio</p>
              </motion.div>
              <motion.h1 className="text-3xl sm:text-5xl font-semibold tracking-tight leading-[1.05]" initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>
                Build agents that <span className="text-gradient-animated">work while you sleep</span>.
              </motion.h1>
              <motion.p className="text-surface-400 mt-3 text-sm sm:text-base max-w-xl" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
                Orchestrate AI agents, workflows, tools & memory in isolated workspaces.
                Explore everything. Nothing is hidden; your data waits for you.
              </motion.p>
              <motion.div className="flex flex-wrap items-center gap-3 mt-6" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
                <Link to="/login" className="btn-primary inline-flex items-center gap-2 px-5 py-2.5">
                  <LogInIcon size={16} />
                  Sign in to save your work
                </Link>
                <Link to="/register" className="btn-secondary inline-flex items-center gap-2">
                  <RocketIcon size={16} />
                  Create an account
                </Link>
              </motion.div>
            </div>
            <motion.div className="hidden lg:block glass-panel p-5 w-72 flex-shrink-0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4, duration: 0.5 }}>
              <p className="microlabel mb-4">how it works</p>
              <div className="space-y-0">
                {PIPELINE.map((step, i) => (
                  <motion.div key={step.label} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 + i * 0.1 }}>
                    <div className="flex items-center gap-3 py-1.5">
                      <div className="w-9 h-9 rounded-xl bg-surface-800/80 border border-surface-700/40 flex items-center justify-center flex-shrink-0">
                        <step.icon size={16} className={step.color} />
                      </div>
                      <span className="text-sm text-surface-300">{step.label}</span>
                      {i === PIPELINE.length - 1 && <CheckIcon size={14} className="text-emerald-400 ml-auto" />}
                    </div>
                    {i < PIPELINE.length - 1 && <div className="flex justify-center"><div className="w-px h-3.5 bg-gradient-to-b from-primary-500/50 to-transparent" /></div>}
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </motion.div>
      )}

      {/* ── Returning users — compact header, straight to data ────── */}
      {isAuthenticated && !showWelcome && (
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="microlabel mb-1.5">dashboard · {todayLong}</p>
            <h1 className="text-2xl font-bold tracking-tight text-surface-100">Overview</h1>
            <p className="text-surface-400 text-sm mt-0.5">
              {established ? 'Here\'s what\'s happening across your studio.' : 'Finish setting up your studio.'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {stats.workspaceCount > 1 && (
              <>
                {stats.workspaces.map((ws: { id: string; name: string }) => (
                  <button
                    key={ws.id}
                    onClick={() => setSelectedWorkspace(ws.id, ws.name)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-sm transition-all',
                      (selectedWorkspaceId || stats.firstWs) === ws.id
                        ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                        : 'bg-surface-800/50 text-surface-400 hover:text-surface-200 border border-surface-700/30',
                    )}
                  >
                    {ws.name}
                  </button>
                ))}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Getting Started checklist — guests & new users ───────── */}
      {showGettingStarted && (
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-5">
            <SparklesIcon size={16} className="text-primary-400" />
            <h2 className="microlabel">Getting Started</h2>
            <div className="ml-auto flex items-center gap-2">
              {isAuthenticated ? (
                <span className="chip">{stepsDone}/{checklistSteps.length} complete</span>
              ) : (
                <span className="text-[11px] text-surface-500">Sign in to unlock creation</span>
              )}
              {isAuthenticated && (
                <button
                  onClick={() => seedDemo()}
                  disabled={seeding}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-primary-500/10 text-primary-400 border border-primary-500/20 hover:bg-primary-500/20 transition-all duration-200 disabled:opacity-50"
                  title="Load a pre-built workspace with a support agent, workflow, prompts and tools"
                >
                  {seeding ? (
                    <div className="w-3 h-3 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
                  ) : (
                    <RocketIcon size={13} />
                  )}
                  {seeding ? 'Loading…' : 'Load demo workspace'}
                </button>
              )}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {checklistSteps.map((step) => (
              <Link
                key={step.key}
                to={step.path}
                className="group flex items-start gap-3 p-4 rounded-xl bg-surface-800/50 border border-surface-700/30 hover:border-primary-500/30 hover:bg-surface-800 transition-all duration-200"
              >
                <div
                  className={cn(
                    'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 border transition-colors duration-200',
                    step.done ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-surface-800/80 border-surface-700/40',
                  )}
                >
                  {step.done ? <CheckIcon size={18} className="text-emerald-400" /> : <step.icon size={18} className={step.color} />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-surface-100 group-hover:text-primary-300 transition-colors duration-200">{step.label}</p>
                  <p className="text-xs text-surface-500 mt-0.5">{step.desc}</p>
                </div>
                <ArrowRightIcon size={15} className="text-surface-600 group-hover:text-primary-400 group-hover:translate-x-0.5 transition-all duration-200 mt-1" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ── Established users — premium data dashboard ────────────── */}
      {established && (
        <>
          {/* Resources */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="microlabel">Resources</h2>
              <span className="h-px flex-1 bg-white/[0.06]" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {resourceCards.map((card) => (
                <Link
                  key={card.label}
                  to={card.path}
                  className="group relative rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 overflow-hidden transition-all duration-200 hover:border-surface-600/40 hover:-translate-y-0.5"
                >
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <div className="flex items-center justify-between mb-4">
                    <div className={cn('w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center shadow-lg shadow-black/20', card.color)}>
                      <card.icon size={18} className="text-white" />
                    </div>
                    <ArrowRightIcon size={15} className="text-surface-600 group-hover:text-primary-400 group-hover:translate-x-1 transition-all duration-200" />
                  </div>
                  <p className="text-3xl font-semibold tracking-tight text-surface-100 tabular-nums">
                    {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
                  </p>
                  <p className="text-sm font-medium text-surface-200 mt-1.5">{card.label}</p>
                  <p className="text-xs text-surface-500 mt-0.5">{card.desc}</p>
                </Link>
              ))}
            </div>
          </section>

          {/* Platform metrics — 7-day usage */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="microlabel">Platform Metrics</h2>
              <span className="h-px flex-1 bg-white/[0.06]" />
              <span className="chip">last 7 days</span>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {platformCards.map((card) => (
                <div
                  key={card.label}
                  className="group relative rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 transition-all duration-200 hover:border-surface-600/40 hover:-translate-y-0.5"
                >
                  <card.icon size={18} className={cn(card.color, 'mb-3')} />
                  <p className="text-2xl font-semibold tracking-tight text-surface-100 tabular-nums">
                    {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
                  </p>
                  <p className="text-xs text-surface-400 mt-1">{card.label}</p>
                  <p className="text-[11px] text-surface-500 mt-0.5">{card.sub}</p>
                </div>
              ))}
            </div>
          </section>

          {/* 7-day activity pulse */}
          {wsStats && (wsStats.telemetryEvents > 0 || wsStats.telemetryErrors > 0) && (
            <section className="glass-panel p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-sm flex items-center gap-2">
                  <span className="relative flex w-2 h-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-40" />
                    <span className="relative inline-flex rounded-full w-2 h-2 bg-emerald-400" />
                  </span>
                  Activity pulse
                </h3>
                <Link to="/telemetry" className="text-xs text-primary-400 hover:text-primary-300 transition-colors flex items-center gap-1">
                  View telemetry <ArrowRightIcon size={11} />
                </Link>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-xl bg-surface-800/40 border border-surface-700/25 p-4">
                  <p className="text-2xl font-bold text-surface-100 tabular-nums">{wsStats.telemetryEvents}</p>
                  <p className="text-xs text-surface-500 mt-1">Events (7d)</p>
                </div>
                <div className="rounded-xl bg-surface-800/40 border border-surface-700/25 p-4">
                  <p className="text-2xl font-bold text-red-400 tabular-nums">{wsStats.telemetryErrors}</p>
                  <p className="text-xs text-surface-500 mt-1">Errors (7d)</p>
                </div>
                <div className="rounded-xl bg-surface-800/40 border border-surface-700/25 p-4">
                  <p className="text-2xl font-bold text-surface-100 tabular-nums">{stats.totalTokens.toLocaleString()}</p>
                  <p className="text-xs text-surface-500 mt-1">Tokens (7d)</p>
                </div>
                <div className="rounded-xl bg-surface-800/40 border border-surface-700/25 p-4">
                  <p className="text-2xl font-bold text-emerald-400 tabular-nums">{stats.totalCost > 0 ? `$${stats.totalCost.toFixed(4)}` : '$0'}</p>
                  <p className="text-xs text-surface-500 mt-1">Spend (7d)</p>
                </div>
              </div>
            </section>
          )}
        </>
      )}

      {/* ── Quick Actions — everyone ──────────────────────────────── */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="microlabel">Quick Actions</h2>
          <span className="h-px flex-1 bg-white/[0.06]" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {QUICK_ACTIONS.map((action) => (
            <Link
              key={action.label}
              to={action.path}
              className="flex flex-col items-center gap-2 px-3 py-4 rounded-xl bg-surface-800/50 border border-surface-700/30 hover:bg-surface-800 hover:border-surface-600/50 transition-all duration-200 group active:scale-[0.98]"
            >
              <action.icon size={20} className={cn(action.color, 'group-hover:scale-110 transition-transform duration-200')} />
              <span className="text-xs text-surface-400 group-hover:text-surface-200 text-center leading-tight">{action.label}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* ── All Domains / Explore the platform ─────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="microlabel">{isAuthenticated ? 'All Domains' : 'Explore the platform'}</h2>
          <span className="h-px flex-1 mx-4 bg-white/[0.06]" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {DOMAIN_LINKS.map((domain) => (
            <Link
              key={domain.path}
              to={domain.path}
              className="card flex items-start gap-4 group hover:border-primary-500/30 hover:-translate-y-0.5 hover:shadow-glass transition-all duration-200"
            >
              <div className="w-10 h-10 rounded-xl bg-surface-800/80 flex items-center justify-center flex-shrink-0 group-hover:bg-primary-500/10 group-hover:border group-hover:border-primary-500/25 transition-all duration-200">
                <domain.icon className={cn('w-5 h-5 text-surface-400', `group-hover:${domain.color}`)} />
              </div>
              <div className="min-w-0">
                <p className="font-medium text-sm group-hover:text-primary-400 transition-colors duration-200">{domain.label}</p>
                <p className="text-xs text-surface-500 mt-0.5">{domain.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}