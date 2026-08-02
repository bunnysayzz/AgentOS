import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ActivityIcon, ArchiveIcon, ArrowRightIcon, BotIcon, BrainIcon, CpuIcon,
  FileTextIcon, KeyIcon, PlusIcon, ServerIcon, UsersIcon, WorkflowIcon,
  GlobeIcon, WrenchIcon, DollarSignIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
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

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const [selectedWsId, setSelectedWsId] = useState<string | null>(null)

  // ─── Global Stats (parallel fetch) ────────────────────────────────
  const globalStatsQuery = useQuery({
    queryKey: ['dashboard-global-stats'],
    queryFn: async () => {
      const [workspacesRes, modelsRes, callsRes, keysRes, providersRes] = await Promise.allSettled([
        api.get('/workspaces/'),
        api.get('/mcp/models'),
        api.get('/mcp/calls'),
        api.get('/api-keys/'),
        api.get('/mcp/providers'),
      ])

      const workspaces = workspacesRes.status === 'fulfilled' ? workspacesRes.value.data : []
      const models = modelsRes.status === 'fulfilled' ? modelsRes.value.data : []
      const calls = callsRes.status === 'fulfilled' ? callsRes.value.data : []
      const keys = keysRes.status === 'fulfilled' ? keysRes.value.data : []
      const providers = providersRes.status === 'fulfilled' ? providersRes.value.data : []

      // Compute derived stats
      const callList = Array.isArray(calls) ? calls : []
      const totalTokens = callList.reduce((s: number, c: any) => s + (c.prompt_tokens || 0) + (c.completion_tokens || 0), 0)
      const totalCost = callList.reduce((s: number, c: any) => s + (c.cost_usd || 0), 0)
      const configuredProviders = Array.isArray(providers) ? providers.filter((p: any) => p.is_configured).length : 0
      const firstWs = Array.isArray(workspaces) && workspaces.length > 0 ? workspaces[0].id : null

      return {
        workspaces: Array.isArray(workspaces) ? workspaces : [],
        workspaceCount: Array.isArray(workspaces) ? workspaces.length : 0,
        modelCount: Array.isArray(models) ? models.length : 0,
        callCount: callList.length,
        totalTokens,
        totalCost,
        keyCount: Array.isArray(keys) ? keys.length : 0,
        configuredProviders,
        firstWs,
      }
    },
    retry: 1,
    staleTime: 30_000,
  })

  const stats = globalStatsQuery.data

  // ─── Workspace-specific stats ─────────────────────────────────────
  const wsId = selectedWsId || stats?.firstWs || ''
  const wsStatsQuery = useQuery({
    queryKey: ['dashboard-ws-stats', wsId],
    queryFn: async () => {
      const [agentsRes, workflowsRes, promptsRes, toolsRes, secretsRes, artifactsRes, telemetryRes] = await Promise.allSettled([
        api.get(`/workspaces/${wsId}/agents/`),
        api.get(`/workspaces/${wsId}/workflows/`),
        api.get(`/workspaces/${wsId}/prompts`),
        api.get(`/workspaces/${wsId}/tools`),
        api.get(`/workspaces/${wsId}/secrets/`),
        api.get(`/workspaces/${wsId}/artifacts/`),
        api.get(`/workspaces/${wsId}/events/stats`, { params: { days: 7 } }),
      ])

      const agents = agentsRes.status === 'fulfilled' ? agentsRes.value.data : []
      const workflows = workflowsRes.status === 'fulfilled' ? workflowsRes.value.data : []
      const prompts = promptsRes.status === 'fulfilled' ? promptsRes.value.data : []
      const tools = toolsRes.status === 'fulfilled' ? toolsRes.value.data : []
      const secrets = secretsRes.status === 'fulfilled' ? secretsRes.value.data : []
      const artifacts = artifactsRes.status === 'fulfilled' ? artifactsRes.value.data : []
      const telemetry = telemetryRes.status === 'fulfilled' ? telemetryRes.value.data : null

      return {
        agentCount: Array.isArray(agents) ? agents.length : 0,
        workflowCount: Array.isArray(workflows) ? workflows.length : 0,
        promptCount: Array.isArray(prompts) ? prompts.length : 0,
        toolCount: Array.isArray(tools) ? tools.length : 0,
        secretCount: Array.isArray(secrets) ? secrets.length : 0,
        artifactCount: Array.isArray(artifacts) ? artifacts.length : 0,
        telemetryEvents: telemetry?.total_events || 0,
        telemetryErrors: telemetry?.errors || 0,
      }
    },
    enabled: !!wsId,
    retry: 1,
    staleTime: 30_000,
  })

  const wsStats = wsStatsQuery.data
  const isLoading = globalStatsQuery.isLoading || wsStatsQuery.isLoading

  // ─── Stat cards ──────────────────────────────────────────────────
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

  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <div>
        <h1 className="text-2xl font-bold">
          Welcome back{user?.fullName ? `, ${user.fullName.split(' ')[0]}` : ''}
        </h1>
        <p className="text-surface-400 mt-1">Here's everything happening in your AgentOS Studio</p>
      </div>

      {/* Workspace selector if multiple */}
      {stats && stats.workspaces.length > 1 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-surface-400">Workspace:</span>
          {stats.workspaces.map((ws: any) => (
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
        <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-3">Resources</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {mainStatCards.filter((c) => c.show).map((card) => (
            <Link
              key={card.label}
              to={card.path}
              className="card group relative overflow-hidden hover:border-surface-600/50 transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${card.color} flex items-center justify-center shadow-lg shadow-black/20`}>
                  <card.icon className="w-5 h-5 text-white" />
                </div>
                <ArrowRightIcon className="w-4 h-4 text-surface-500 group-hover:text-surface-300 transition-colors" />
              </div>
              <p className="text-2xl font-bold">
                {isLoading ? (
                  <div className="w-10 h-7 bg-surface-800 rounded animate-pulse" />
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
        <h2 className="text-sm font-medium text-surface-400 uppercase tracking-wider mb-3">Platform Metrics</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {secondaryStatCards.map((card) => (
            <div key={card.label} className="card">
              <card.icon size={18} className={`${card.color} mb-2`} />
              <p className="text-2xl font-bold">{isLoading ? <div className="w-10 h-7 bg-surface-800 rounded animate-pulse inline-block" /> : card.value}</p>
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

      {/* Quick Actions */}
      <div className="glass-panel p-6">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {QUICK_ACTIONS.map((action) => (
            <Link
              key={action.label}
              to={action.path}
              className="flex flex-col items-center gap-2 px-3 py-4 rounded-xl bg-surface-800/50 border border-surface-700/30 hover:bg-surface-800 hover:border-surface-600/50 transition-all duration-200 group"
            >
              <action.icon size={20} className={`${action.color} group-hover:scale-110 transition-transform duration-200`} />
              <span className="text-xs text-surface-400 group-hover:text-surface-200 text-center leading-tight">{action.label}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* All Domains */}
      <div>
        <h2 className="text-lg font-semibold mb-4">All Domains</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {DOMAIN_LINKS.map((domain) => (
            <Link
              key={domain.path}
              to={domain.path}
              className="card flex items-start gap-4 group hover:border-surface-600/50 transition-all duration-200"
            >
              <div className="w-10 h-10 rounded-xl bg-surface-800 flex items-center justify-center flex-shrink-0 group-hover:bg-primary-500/10 transition-all duration-200">
                <domain.icon className={`w-5 h-5 text-surface-400 group-hover:${domain.color} transition-colors duration-200`} />
              </div>
              <div className="min-w-0">
                <p className="font-medium text-sm group-hover:text-primary-400 transition-colors duration-200">
                  {domain.label}
                </p>
                <p className="text-xs text-surface-500 mt-0.5">{domain.desc}</p>
              </div>
            </Link>
          ))}
        </div>
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
