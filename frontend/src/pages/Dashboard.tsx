import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ActivityIcon, ArchiveIcon, ArrowRightIcon, BotIcon, BrainIcon, CheckCircleIcon,
  CheckIcon, CpuIcon, FileTextIcon, KeyIcon, LogInIcon, LogoIcon, PlusIcon,
  RocketIcon, ServerIcon, SparklesIcon, UsersIcon, WorkflowIcon,
  GlobeIcon, WrenchIcon, DollarSignIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { cn } from '@/utils/cn'

const QUICK_ACTIONS = [
  { label: 'New Workspace', icon: PlusIcon, color: 'text-primary-400', path: '/workspaces' },
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
  { label: 'Execution Graphs', icon: ServerIcon, path: '/graphs', desc: 'Node-level execution tracing', color: 'text-violet-400' },
  { label: 'API Keys', icon: KeyIcon, path: '/api-keys', desc: 'Programmatic access management', color: 'text-amber-400' },
  { label: 'Providers', icon: GlobeIcon, path: '/providers', desc: 'AI provider configuration', color: 'text-sky-400' },
  { label: 'Memory', icon: BrainIcon, path: '/memory', desc: 'Conversation & session memory', color: 'text-pink-400' },
]

// How-it-works pipeline shown to guests in the hero
const PIPELINE = [
  { label: 'Prompt', icon: FileTextIcon, color: 'text-amber-400' },
  { label: 'Agent', icon: BotIcon, color: 'text-primary-400' },
  { label: 'Tools', icon: WrenchIcon, color: 'text-sky-400' },
  { label: 'Output', icon: CheckCircleIcon, color: 'text-emerald-400' },
]

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const setSelectedWorkspace = useWorkspaceStore((s) => s.setSelectedWorkspace)
  const [selectedWsId, setSelectedWsId] = useState<string | null>(null)

  // One-click demo workspace for first-run users.
  const { mutate: seedDemo, isPending: seeding } = useMutation({
    mutationFn: () => api.post('/demo/seed').then((r) => r.data),
    onSuccess: (data: { id: string; name: string }) => {
      // Invalidate the workspace + stats queries AND the per-domain list
      // caches so the freshly seeded agents/workflows/prompts/tools appear
      // immediately instead of stale empty lists.
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
  // The server computes every count (workspaces, models, calls, keys,
  // providers + per-workspace tallies) with aggregate Firestore queries,
  // replacing the old ~12 parallel list fetches that downloaded entire
  // collections just to display numbers.
  const globalStatsQuery = useQuery({
    queryKey: ['dashboard-stats', selectedWsId],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/stats', {
        params: selectedWsId ? { workspace_id: selectedWsId, days: 7 } : { days: 7 },
      })
      const d = data || {}
      const workspaces: { id: string; name: string }[] = Array.isArray(d.workspaces) ? d.workspaces : []
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
        // Per-workspace tallies (server-aggregated)
        ws: d.workspace || null,
      }
    },
    retry: 1,
    staleTime: 30_000,
  })

  const stats = globalStatsQuery.data

  // Workspace-specific stats ride along in the same aggregate response — no
  // second round of fetches when the user switches workspaces.
  const wsStats = stats?.ws
  const wsId = selectedWsId || stats?.firstWs || ''
  const isLoading = globalStatsQuery.isLoading

  // ─── Onboarding state ─────────────────────────────────────────────
  // Guests get the full "getting started" experience; authed users with
  // no workspace yet get the same checklist so the zero-state feels
  // intentional instead of broken.
  const isNewUser = isAuthenticated && (stats?.workspaceCount ?? 0) === 0
  const showGettingStarted = !isAuthenticated || isNewUser

  const checklistSteps = [
    {
      key: 'workspace', label: 'Create a workspace',
      desc: 'Your isolated home for agents, workflows & data',
      icon: UsersIcon, color: 'text-primary-400', path: '/workspaces',
      done: (stats?.workspaceCount ?? 0) > 0,
    },
    {
      key: 'provider', label: 'Connect an AI provider',
      desc: 'Add OpenAI, Anthropic or Gemini keys',
      icon: GlobeIcon, color: 'text-sky-400', path: '/providers',
      done: (stats?.configuredProviders ?? 0) > 0,
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

  // ─── Stat cards (authed users with data) ──────────────────────────
  const mainStatCards = [
    {
      label: 'Workspaces', icon: UsersIcon, color: 'from-primary-500 to-primary-600',
      value: stats?.workspaceCount ?? '—', path: '/workspaces', show: true,
    },
    {
      label: 'Agents', icon: BotIcon, color: 'from-emerald-500 to-emerald-600',
      value: wsStats?.agentCount ?? '—', path: '/agents', show: !!wsId,
    },
    {
      label: 'Workflows', icon: WorkflowIcon, color: 'from-violet-500 to-violet-600',
      value: wsStats?.workflowCount ?? '—', path: '/workflows', show: !!wsId,
    },
    {
      label: 'Prompts', icon: FileTextIcon, color: 'from-amber-500 to-amber-600',
      value: wsStats?.promptCount ?? '—', path: '/prompts', show: !!wsId,
    },
    {
      label: 'Tools', icon: WrenchIcon, color: 'from-rose-500 to-rose-600',
      value: wsStats?.toolCount ?? '—', path: '/tools', show: !!wsId,
    },
    {
      label: 'Secrets', icon: KeyIcon, color: 'from-cyan-500 to-cyan-600',
      value: wsStats?.secretCount ?? '—', path: '/secrets', show: !!wsId,
    },
    {
      label: 'Artifacts', icon: ArchiveIcon, color: 'from-indigo-500 to-indigo-600',
      value: wsStats?.artifactCount ?? '—', path: '/artifacts', show: !!wsId,
    },
  ]

  const secondaryStatCards = [
    {
      label: 'LLM Models', icon: CpuIcon, color: 'text-sky-400',
      value: stats?.modelCount ?? '—', sub: `${stats?.callCount || 0} calls made`,
    },
    {
      label: 'API Keys', icon: KeyIcon, color: 'text-amber-400',
      value: stats?.keyCount ?? '—', sub: 'For programmatic access',
    },
    {
      label: 'Providers', icon: GlobeIcon, color: 'text-emerald-400',
      value: stats?.configuredProviders ?? '—', sub: 'Configured & active',
    },
    {
      label: 'Total Cost', icon: DollarSignIcon, color: 'text-rose-400',
      value: stats?.totalCost ? `$${stats.totalCost.toFixed(6)}` : '$0', sub: `${stats?.totalTokens?.toLocaleString() || 0} tokens`,
    },
  ]

  // ─── Stagger presets for card grids (industry-level entrance) ────
  const staggerContainer = {
    hidden: {},
    show: { transition: { staggerChildren: 0.05, delayChildren: 0.04 } },
  }
  const staggerItem = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const } },
  }

  return (
    <div className="space-y-8">
      {/* ── Welcome Header — guest-aware, single CTA ─────────────── */}
      <motion.div 
        className="relative overflow-hidden rounded-3xl border border-white/[0.06] bg-gradient-to-br from-white/[0.04] to-transparent p-6 sm:p-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* Animated background orbs */}
        <motion.div 
          className="absolute -top-24 -right-16 w-72 h-72 rounded-full bg-primary-500/10 blur-3xl pointer-events-none" 
          animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.8, 0.5] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden 
        />
        <motion.div 
          className="absolute -bottom-32 -left-20 w-96 h-96 rounded-full bg-info/10 blur-3xl pointer-events-none" 
          animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          aria-hidden 
        />
        <motion.div 
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full bg-emerald-500/5 blur-3xl pointer-events-none" 
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          aria-hidden 
        />
        <div className="relative flex flex-col lg:flex-row lg:items-center gap-8">
          <div className="flex-1 min-w-0">
            <motion.div 
              className="flex items-center gap-3 mb-4"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              <motion.div 
                className="w-11 h-11 rounded-2xl bg-gradient-to-br from-[#16151a] to-[#08080b] border border-primary-600/40 flex items-center justify-center shadow-lg shadow-primary-500/25 flex-shrink-0"
                whileHover={{ scale: 1.05, rotate: 5 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
              >
                <LogoIcon size={22} />
              </motion.div>
              <p className="microlabel">agent orchestration studio</p>
            </motion.div>
            {isAuthenticated ? (
              <>
                <motion.h1 
                  className="text-2xl sm:text-3xl font-semibold tracking-tight"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, duration: 0.4 }}
                >
                  Welcome back{user?.fullName ? `, ${user.fullName.split(' ')[0]}` : ''}
                </motion.h1>
                <motion.p 
                  className="text-surface-400 mt-2 text-sm"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4 }}
                >
                  Here's everything happening in your AgentOS Studio
                </motion.p>
              </>
            ) : (
              <>
                <motion.h1 
                  className="text-3xl sm:text-5xl font-semibold tracking-tight leading-[1.05]"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, duration: 0.5 }}
                >
                  Build agents that <span className="text-gradient-animated">work while you sleep</span>.
                </motion.h1>
                <motion.p 
                  className="text-surface-400 mt-3 text-sm sm:text-base max-w-xl"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 }}
                >
                  Orchestrate AI agents, workflows, tools & memory in isolated workspaces.
                  Explore everything. Nothing is hidden; your data waits for you.
                </motion.p>
                <motion.div 
                  className="flex flex-wrap items-center gap-3 mt-6"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.6 }}
                >
                  <Link
                    to="/login"
                    className="btn-primary inline-flex items-center gap-2 px-5 py-2.5"
                  >
                    <LogInIcon size={16} />
                    Sign in to save your work
                  </Link>
                  <Link
                    to="/register"
                    className="btn-secondary inline-flex items-center gap-2"
                  >
                    <RocketIcon size={16} />
                    Create an account
                  </Link>
                </motion.div>
              </>
            )}
          </div>

          {/* How-it-works pipeline — guest only */}
          {!isAuthenticated && (
            <motion.div 
              className="hidden lg:block glass-panel p-5 w-72 flex-shrink-0"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <p className="microlabel mb-4">how it works</p>
              <div className="space-y-0">
                {PIPELINE.map((step, i) => (
                  <motion.div 
                    key={step.label}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + i * 0.1 }}
                  >
                    <div className="flex items-center gap-3 py-1.5">
                      <motion.div 
                        className="w-9 h-9 rounded-xl bg-surface-800/80 border border-surface-700/40 flex items-center justify-center flex-shrink-0"
                        whileHover={{ scale: 1.1, borderColor: "rgba(139, 92, 246, 0.35)" }}
                      >
                        <step.icon size={16} className={step.color} />
                      </motion.div>
                      <span className="text-sm text-surface-300">{step.label}</span>
                      {i === PIPELINE.length - 1 && (
                        <motion.div
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ delay: 0.9, type: "spring", stiffness: 300 }}
                        >
                          <CheckIcon size={14} className="text-emerald-400 ml-auto" />
                        </motion.div>
                      )}
                    </div>
                    {i < PIPELINE.length - 1 && (
                      <div className="flex justify-center">
                        <motion.div 
                          className="w-px h-3.5 bg-gradient-to-b from-primary-500/50 to-transparent"
                          initial={{ scaleY: 0 }}
                          animate={{ scaleY: 1 }}
                          transition={{ delay: 0.6 + i * 0.1, duration: 0.3 }}
                          style={{ transformOrigin: 'top' }}
                        />
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* ── Getting Started checklist — guests & new users ───────── */}
      {showGettingStarted && (
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-5">
            <SparklesIcon size={16} className="text-primary-400" />
            <h2 className="microlabel">Getting Started</h2>
            <div className="ml-auto flex items-center gap-2">
              {isAuthenticated ? (
                <span className="chip">
                  {stepsDone}/{checklistSteps.length} complete
                </span>
              ) : (
                <span className="text-[11px] text-surface-500">
                  Sign in to unlock creation
                </span>
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
                    step.done
                      ? 'bg-emerald-500/10 border-emerald-500/30'
                      : 'bg-surface-800/80 border-surface-700/40',
                  )}
                >
                  {step.done
                    ? <CheckIcon size={18} className="text-emerald-400" />
                    : <step.icon size={18} className={step.color} />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-surface-100 group-hover:text-primary-300 transition-colors duration-200">
                    {step.label}
                  </p>
                  <p className="text-xs text-surface-500 mt-0.5">{step.desc}</p>
                </div>
                <ArrowRightIcon
                  size={15}
                  className="text-surface-600 group-hover:text-primary-400 group-hover:translate-x-0.5 transition-all duration-200 mt-1"
                />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ── Stats — only for authenticated users with a workspace ── */}
      {isAuthenticated && !isNewUser && (
        <>
          {/* Workspace selector if multiple */}
          {stats && stats.workspaces.length > 1 && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-sm text-surface-400">Workspace:</span>
              {stats.workspaces.map((ws: { id: string; name: string }) => (
                <button
                  key={ws.id}
                  onClick={() => setSelectedWsId(ws.id)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm transition-all',
                    (selectedWsId || stats.firstWs) === ws.id
                      ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'bg-surface-800/50 text-surface-400 hover:text-surface-200 border border-surface-700/30',
                  )}
                >
                  {ws.name}
                </button>
              ))}
            </div>
          )}

          {/* Main Stats Grid */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="microlabel">Resources</h2>
              <span className="h-px flex-1 mx-4 bg-white/[0.06]" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {mainStatCards.filter((c) => c.show).map((card) => (
                <Link
                  key={card.label}
                  to={card.path}
                  className="group relative rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 transition-all duration-200 hover:border-surface-600/40 hover:-translate-y-0.5"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${card.color} flex items-center justify-center shadow-lg shadow-black/20`}> 
                      <card.icon className="w-5 h-5 text-white" />
                    </div>
                    <ArrowRightIcon className="w-4 h-4 text-surface-500 group-hover:text-primary-400 group-hover:translate-x-1 transition-all duration-200" />
                  </div>
                  <p className="text-2xl font-semibold tracking-tight">
                    {isLoading ? (
                      <span className="inline-block w-10 h-7 bg-surface-800 rounded animate-pulse" />
                    ) : (
                      <span>{typeof card.value === 'number' ? card.value.toLocaleString() : card.value}</span>
                    )}
                  </p>
                  <p className="text-sm text-surface-400 mt-0.5">{card.label}</p>
                </Link>
              ))}
            </div>
          </div>

          {/* Secondary Stats */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="microlabel">Platform Metrics</h2>
              <span className="h-px flex-1 mx-4 bg-white/[0.06]" />
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {secondaryStatCards.map((card) => (
                <div key={card.label} className="rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 hover:border-surface-600/40 hover:-translate-y-0.5 transition-all duration-200">
                  <card.icon size={18} className={`${card.color} mb-2`} />
                  <p className="text-2xl font-semibold tracking-tight">{isLoading ? <span className="inline-block w-10 h-7 bg-surface-800 rounded animate-pulse" /> : card.value}</p>
                  <p className="text-xs text-surface-500 mt-0.5">{card.sub}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Telemetry Quick Summary (if available) */}
          {wsStats && (wsStats.telemetryEvents > 0 || wsStats.telemetryErrors > 0) && (
            <div className="glass-panel p-5">
              <h3 className="font-medium mb-3 flex items-center gap-2">
                <ActivityIcon size={16} className="text-emerald-400" />
                Recent Activity (7 days)
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-2xl font-bold text-surface-100">{wsStats.telemetryEvents}</p>
                  <p className="text-xs text-surface-500">Total Events</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-400">{wsStats.telemetryErrors}</p>
                  <p className="text-xs text-surface-500">Errors</p>
                </div>
                <div className="md:col-span-2 flex items-end justify-end">
                  <Link to="/telemetry" className="text-sm text-primary-400 hover:text-primary-300 transition-colors flex items-center gap-1">
                    View details <ArrowRightIcon size={12} />
                  </Link>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Quick Actions ─────────────────────────────────────────── */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="microlabel">Quick Actions</h2>
          <span className="h-px flex-1 bg-white/[0.06]" />
        </div>
        <motion.div
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3"
          variants={staggerContainer}
          initial="hidden"
          animate="show"
        >
          {QUICK_ACTIONS.map((action) => (
            <motion.div key={action.label} variants={staggerItem}>
            <Link
              to={action.path}
              className="flex flex-col items-center gap-2 px-3 py-4 rounded-xl bg-surface-800/50 border border-surface-700/30 hover:bg-surface-800 hover:border-surface-600/50 transition-all duration-200 group"
            >
              <action.icon size={20} className={`${action.color} group-hover:scale-110 transition-transform duration-200`} />
              <span className="text-xs text-surface-400 group-hover:text-surface-200 text-center leading-tight">{action.label}</span>
            </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* ── All Domains / Explore the platform ─────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="microlabel">
            {isAuthenticated ? 'All Domains' : 'Explore the platform'}
          </h2>
          <span className="h-px flex-1 mx-4 bg-white/[0.06]" />
        </div>
        <motion.div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
          variants={staggerContainer}
          initial="hidden"
          animate="show"
        >
          {DOMAIN_LINKS.map((domain) => (
            <motion.div key={domain.path} variants={staggerItem}>
            <Link
              to={domain.path}
              className="card flex items-start gap-4 group hover:border-primary-500/30 hover:-translate-y-0.5 hover:shadow-glass transition-all duration-200"
            >
              <div className="w-10 h-10 rounded-xl bg-surface-800/80 flex items-center justify-center flex-shrink-0 group-hover:bg-primary-500/10 group-hover:border group-hover:border-primary-500/25 transition-all duration-200">
                <domain.icon className={`w-5 h-5 text-surface-400 group-hover:${domain.color} transition-colors duration-200`} />
              </div>
              <div className="min-w-0">
                <p className="font-medium text-sm group-hover:text-primary-400 transition-colors duration-200">
                  {domain.label}
                </p>
                <p className="text-xs text-surface-500 mt-0.5">{domain.desc}</p>
              </div>
            </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Global loading overlay */}
      {globalStatsQuery.isLoading && (
        <div className="fixed bottom-4 right-4 flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-800 border border-surface-700/50 shadow-lg">
          <div className="w-3 h-3 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
          <span className="text-xs text-surface-400">Loading dashboard...</span>
        </div>
      )}
    </div>
  )
}
