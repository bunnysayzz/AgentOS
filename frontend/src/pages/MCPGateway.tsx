import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  ActivityIcon, ArrowRightIcon, CheckCircleIcon, ClockIcon,
  CopyIcon, CpuIcon, DatabaseIcon, DollarSignIcon, GlobeIcon,
  MessageSquareIcon, PhoneIcon, RefreshCwIcon,
} from '@/components/Icons'
import api from '@/services/api'
import ChatInterface from '@/components/ChatInterface'
import PageHeader from '@/components/PageHeader'
import EmptyState from '@/components/EmptyState'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface Model { id: string; model_name: string; provider: string; input_price_per_1k: number; output_price_per_1k: number; is_active: boolean }
interface Call { id: string; model_name: string; provider: string; prompt_tokens: number; completion_tokens: number; cost_usd: number; created_at: string; status: string }
interface MarketplaceServer {
  id: string; name: string; description: string; command: string;
  args: string[]; env_vars: string[]; homepage: string; category: string
}

type TabId = 'chat' | 'models' | 'calls' | 'costs' | 'servers'

const TABS: { id: TabId; label: string; icon: React.FC<{ size?: number; className?: string }> }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquareIcon },
  { id: 'models', label: 'Models', icon: CpuIcon },
  { id: 'calls', label: 'Calls', icon: PhoneIcon },
  { id: 'costs', label: 'Costs', icon: DollarSignIcon },
  { id: 'servers', label: 'Servers', icon: DatabaseIcon },
]

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google Gemini',
  groq: 'Groq', mistral: 'Mistral AI', deepseek: 'DeepSeek',
  openrouter: 'OpenRouter', cerebras: 'Cerebras',
  huggingface: 'HuggingFace', together_ai: 'Together AI',
  ollama: 'Ollama', azure: 'Azure OpenAI',
  agentrouter: 'AgentRouter', custom: 'Custom',
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'from-emerald-500 to-emerald-600',
  anthropic: 'from-amber-500 to-amber-600',
  google: 'from-blue-500 to-blue-600',
  groq: 'from-purple-500 to-purple-600',
  cerebras: 'from-orange-500 to-orange-600',
  openrouter: 'from-rose-500 to-rose-600',
  mistral: 'from-sky-500 to-sky-600',
  deepseek: 'from-blue-700 to-indigo-700',
  agentrouter: 'from-violet-500 to-indigo-600',
  custom: 'from-surface-500 to-surface-600',
}

const CATEGORY_COLORS: Record<string, string> = {
  storage: 'text-sky-400 bg-sky-500/10 border-sky-500/15',
  dev: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/15',
  browser: 'text-violet-400 bg-violet-500/10 border-violet-500/15',
  data: 'text-amber-400 bg-amber-500/10 border-amber-500/15',
  automation: 'text-rose-400 bg-rose-500/10 border-rose-500/15',
}

function providerLabel(p: string) { return PROVIDER_LABELS[p] || p.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()) }
function providerColor(p: string) { return PROVIDER_COLORS[p] || 'from-surface-600 to-surface-700' }

function fmtUsd(n: number) {
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n > 0) return `$${n.toFixed(6)}`
  return '$0'
}

// ─── Shared building blocks ──────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: React.FC<{ size?: number; className?: string }>
  label: string; value: React.ReactNode; sub?: string
  color: string
}) {
  return (
    <div className="group relative rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 transition-all duration-200 hover:border-surface-600/40 hover:-translate-y-0.5">
      <div className="flex items-center justify-between mb-4">
        <div className={cn('w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center shadow-lg shadow-black/20', color)}>
          <Icon size={18} className="text-white" />
        </div>
      </div>
      <p className="text-2xl font-semibold tracking-tight text-surface-100">{value}</p>
      <p className="text-sm text-surface-400 mt-0.5">{label}</p>
      {sub && <p className="text-xs text-surface-500 mt-1">{sub}</p>}
    </div>
  )
}

function TabSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <div className="space-y-4 animate-pulse" aria-busy="true">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {Array.from({ length: cards }).map((_, i) => (
          <div key={i} className="h-32 rounded-2xl bg-surface-800/40 border border-surface-700/20" />
        ))}
      </div>
      <div className="grid gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 rounded-2xl bg-surface-800/40 border border-surface-700/20" />
        ))}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase() || ''
  const styles =
    s === 'error' || s === 'failed'
      ? 'text-red-400 bg-red-500/10 border-red-500/20'
      : s === 'running' || s === 'pending'
        ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
        : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
  const label = s === 'error' || s === 'failed' ? 'Failed' : s === 'running' || s === 'pending' ? 'Running' : 'Success'
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border', styles)}>
      <span className={cn('w-1 h-1 rounded-full', s === 'error' || s === 'failed' ? 'bg-red-400' : s === 'running' || s === 'pending' ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400')} />
      {label}
    </span>
  )
}

export default function MCPGateway() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabId>('chat')

  const marketplaceQuery = useQuery({
    queryKey: ['mcp-marketplace'],
    queryFn: () => api.get('/mcp/marketplace').then((r) => r.data),
    staleTime: 30 * 60_000,
  })
  const serverList: MarketplaceServer[] = Array.isArray(marketplaceQuery.data) ? marketplaceQuery.data : []

  const modelsQuery = useQuery({
    queryKey: ['mcp-models'],
    queryFn: () => api.get('/mcp/models').then((r) => r.data),
  })
  const callsQuery = useQuery({
    queryKey: ['mcp-calls'],
    queryFn: () => api.get('/mcp/calls').then((r) => r.data),
  })

  const { mutate: seedModels, isPending: seeding } = useMutation({
    mutationFn: () => api.post('/mcp/models/seed').then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mcp-models'] })
      qc.invalidateQueries({ queryKey: ['mcp-costs'] })
      toast.success('Models seeded', 'Default LLM models loaded.')
    },
  })

  const copyServerConfig = async (server: MarketplaceServer) => {
    const lines = [
      `# ${server.name}`,
      `# ${server.description}`,
      `"${server.command}", ${server.args.map((a) => `"${a}"`).join(', ')}`,
      ...(server.env_vars.length ? [`# env: ${server.env_vars.join(', ')}`] : []),
    ]
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      toast.success('Config copied', `${server.name} command copied to clipboard.`)
    } catch {
      toast.error('Copy failed', 'Clipboard not available in this browser.')
    }
  }

  const modelList: Model[] = modelsQuery.data?.models || (Array.isArray(modelsQuery.data) ? modelsQuery.data : [])
  const callList: Call[] = Array.isArray(callsQuery.data) ? callsQuery.data : []

  const totalTokens = callList.reduce((s, c) => s + (c.prompt_tokens || 0) + (c.completion_tokens || 0), 0)
  const totalCost = callList.reduce((s, c) => s + (c.cost_usd || 0), 0)
  const recentCalls = callList.slice(-5).reverse()
  const activeModels = modelList.filter((m) => m.is_active).length

  // Per-model cost breakdown for the Costs tab
  const byModel = useMemo(() => {
    const map = new Map<string, { cost: number; tokens: number; calls: number }>()
    for (const c of callList) {
      const cur = map.get(c.model_name) || { cost: 0, tokens: 0, calls: 0 }
      cur.cost += c.cost_usd || 0
      cur.tokens += (c.prompt_tokens || 0) + (c.completion_tokens || 0)
      cur.calls += 1
      map.set(c.model_name, cur)
    }
    return [...map.entries()].sort((a, b) => b[1].cost - a[1].cost)
  }, [callList])

  return (
    <div className="space-y-6">
      <PageHeader
        title="MCP Gateway"
        subtitle="LLM model routing, pricing, and cost tracking"
        icon={<CpuIcon size={19} className="text-primary-400" />}
      />

      {/* Tabs — animated pill follows the active tab */}
      <div className="flex gap-1 p-1 rounded-2xl bg-surface-800/40 border border-surface-700/20 w-fit flex-wrap">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'relative px-4 py-2 rounded-xl text-sm font-medium transition-colors duration-150',
              tab === t.id ? 'text-white' : 'text-surface-400 hover:text-surface-200',
            )}
          >
            {tab === t.id && (
              <motion.span
                layoutId="mcp-tab-pill"
                className="absolute inset-0 rounded-xl bg-gradient-to-b from-primary-500/90 to-primary-600/80 shadow-lg shadow-primary-500/25"
                transition={{ type: 'spring', stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-1.5">
              <t.icon size={14} />
              {t.label}
            </span>
          </button>
        ))}
      </div>

      {/* ── CHAT ── */}
      {tab === 'chat' && (
        <ChatInterface
          title="MCP Chat"
          height="min(600px, 80vh)"
          showProviderSelector={true}
          placeholder="Ask the AI anything..."
        />
      )}

      {/* ── MODELS ── */}
      {tab === 'models' && (
        <div className="grid gap-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard icon={CpuIcon} label="Total Models" value={modelList.length} sub="in the catalog" color="from-primary-500 to-primary-600" />
            <StatCard icon={CheckCircleIcon} label="Active" value={activeModels} sub="ready to route" color="from-emerald-500 to-emerald-600" />
            <StatCard icon={ActivityIcon} label="Total Calls" value={callList.length} sub="all time" color="from-amber-500 to-amber-600" />
            <StatCard icon={DollarSignIcon} label="Total Cost" value={fmtUsd(totalCost)} sub={`${totalTokens.toLocaleString()} tokens`} color="from-rose-500 to-rose-600" />
          </div>

          {modelsQuery.isLoading ? (
            <TabSkeleton />
          ) : modelList.length === 0 ? (
            <EmptyState
              icon={<CpuIcon size={26} />}
              title="No models loaded"
              description="Populate the catalog with the default LLM models to start routing calls."
              action={
                <button onClick={() => seedModels()} disabled={seeding} className="btn-primary flex items-center gap-2 mx-auto">
                  {seeding ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <DatabaseIcon size={15} />
                  )}
                  {seeding ? 'Seeding…' : 'Seed Models'}
                </button>
              }
            />
          ) : (
            <>
              <div className="flex justify-end">
                <button onClick={() => seedModels()} disabled={seeding} className="btn-secondary flex items-center gap-2 text-sm">
                  {seeding ? <RefreshCwIcon size={14} className="animate-spin" /> : <DatabaseIcon size={14} />}
                  Seed Models
                </button>
              </div>
              <div className="grid gap-2">
                {modelList.map((m) => (
                  <div key={m.id} className="group rounded-2xl bg-gradient-to-b from-surface-800/50 to-surface-800/25 border border-surface-700/25 hover:border-surface-600/40 transition-all duration-200 p-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4 min-w-0">
                      <div className={cn('w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center flex-shrink-0', providerColor(m.provider))}>
                        <CpuIcon size={16} className="text-white" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-sm text-surface-100 truncate">{m.model_name}</p>
                          <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', m.is_active ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]' : 'bg-surface-600')} title={m.is_active ? 'Active' : 'Inactive'} />
                        </div>
                        <p className="text-xs text-surface-500 mt-0.5">{providerLabel(m.provider)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="px-2.5 py-1 rounded-lg bg-surface-900/60 border border-surface-700/30 text-[11px] font-mono text-surface-300">
                        <span className="text-surface-500">in </span>${m.input_price_per_1k}/1K
                      </span>
                      <span className="px-2.5 py-1 rounded-lg bg-surface-900/60 border border-surface-700/30 text-[11px] font-mono text-surface-300">
                        <span className="text-surface-500">out </span>${m.output_price_per_1k}/1K
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── CALLS ── */}
      {tab === 'calls' && (
        <div className="grid gap-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard icon={PhoneIcon} label="Total Calls" value={callList.length} sub="all time" color="from-primary-500 to-primary-600" />
            <StatCard icon={ActivityIcon} label="Total Tokens" value={totalTokens.toLocaleString()} sub="in + out" color="from-amber-500 to-amber-600" />
            <StatCard icon={DollarSignIcon} label="Total Cost" value={fmtUsd(totalCost)} sub={`avg ${callList.length ? (totalCost / callList.length).toFixed(6) : '0.000000'}/call`} color="from-emerald-500 to-emerald-600" />
            <StatCard icon={ClockIcon} label="Latest Call" value={recentCalls.length > 0 ? recentCalls[0].created_at?.slice(0, 10) : '—'} sub={recentCalls[0]?.model_name || 'no activity yet'} color="from-sky-500 to-sky-600" />
          </div>

          {callsQuery.isLoading ? (
            <TabSkeleton />
          ) : callList.length === 0 ? (
            <EmptyState
              icon={<PhoneIcon size={26} />}
              title="No calls yet"
              description="Start a chat or run an agent to see LLM calls tracked here."
              action={
                <button onClick={() => setTab('chat')} className="btn-primary flex items-center gap-2 mx-auto">
                  <MessageSquareIcon size={15} />
                  Open Chat
                </button>
              }
            />
          ) : (
            <div className="grid gap-2">
              {callList.map((c) => (
                <div key={c.id} className="rounded-2xl bg-gradient-to-b from-surface-800/50 to-surface-800/25 border border-surface-700/25 hover:border-surface-600/40 transition-all duration-200 p-4 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className={cn('w-9 h-9 rounded-xl bg-gradient-to-br flex items-center justify-center flex-shrink-0', providerColor(c.provider))}>
                      <CpuIcon size={14} className="text-white" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium text-sm text-surface-100 truncate">{c.model_name}</p>
                        <StatusBadge status={c.status} />
                      </div>
                      <p className="text-xs text-surface-500 mt-0.5">
                        {providerLabel(c.provider)} · {((c.prompt_tokens || 0) + (c.completion_tokens || 0)).toLocaleString()} tokens
                      </p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-semibold text-surface-100">{fmtUsd(c.cost_usd)}</p>
                    <p className="text-xs text-surface-500 mt-0.5">{c.created_at?.slice(0, 10)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── COSTS ── */}
      {tab === 'costs' && (
        <div className="grid gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <StatCard icon={DollarSignIcon} label="Lifetime Spend" value={fmtUsd(totalCost)} sub={`${callList.length} calls tracked`} color="from-emerald-500 to-emerald-600" />
            <StatCard icon={ActivityIcon} label="Tokens Processed" value={totalTokens.toLocaleString()} sub={`${byModel.length} model${byModel.length !== 1 ? 's' : ''} in use`} color="from-amber-500 to-amber-600" />
          </div>

          {callsQuery.isLoading ? (
            <TabSkeleton cards={2} />
          ) : byModel.length === 0 ? (
            <EmptyState
              icon={<DollarSignIcon size={26} />}
              title="No cost data yet"
              description="Cost data appears after you make LLM calls through the chat."
              action={
                <button onClick={() => setTab('chat')} className="btn-primary flex items-center gap-2 mx-auto">
                  <MessageSquareIcon size={15} />
                  Start Chatting
                </button>
              }
            />
          ) : (
            <div className="glass-panel p-5">
              <div className="flex items-center gap-2 mb-4">
                <DollarSignIcon size={15} className="text-primary-400" />
                <h3 className="font-medium text-sm text-surface-100">Spend by model</h3>
                <span className="h-px flex-1 bg-white/[0.06]" />
              </div>
              <div className="space-y-4">
                {byModel.map(([name, stat]) => {
                  const pct = totalCost > 0 ? (stat.cost / totalCost) * 100 : 0
                  return (
                    <div key={name}>
                      <div className="flex items-center justify-between mb-1.5 gap-3">
                        <p className="text-sm text-surface-200 truncate font-medium">{name}</p>
                        <div className="flex items-center gap-3 flex-shrink-0 text-xs">
                          <span className="text-surface-500">{stat.calls} call{stat.calls !== 1 ? 's' : ''} · {stat.tokens.toLocaleString()} tok</span>
                          <span className="font-mono text-surface-200">{fmtUsd(stat.cost)}</span>
                          <span className="w-10 text-right text-surface-500 font-mono">{pct.toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className="h-1.5 rounded-full bg-surface-800/80 overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-gradient-to-r from-primary-500 to-primary-400"
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(pct, 1)}%` }}
                          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── SERVERS ── */}
      {tab === 'servers' && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <h2 className="microlabel">Popular MCP servers</h2>
            <span className="h-px flex-1 bg-white/[0.06]" />
            <span className="chip">{serverList.length} available</span>
          </div>
          {marketplaceQuery.isLoading ? (
            <TabSkeleton cards={3} />
          ) : serverList.length === 0 ? (
            <EmptyState
              icon={<DatabaseIcon size={26} />}
              title="No servers available"
              description="The marketplace catalog is empty right now."
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {serverList.map((server) => (
                <div key={server.id} className="group flex flex-col rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/25 border border-surface-700/25 hover:border-primary-500/25 hover:-translate-y-0.5 transition-all duration-200 p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-indigo-500/15 border border-violet-500/15 flex items-center justify-center flex-shrink-0">
                        <DatabaseIcon size={18} className="text-violet-400" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-sm text-surface-100 truncate">{server.name}</p>
                        <span className={cn(
                          'inline-flex mt-1 px-2 py-0.5 rounded-full text-[10px] font-medium capitalize border',
                          CATEGORY_COLORS[server.category] || 'text-surface-400 bg-surface-800/60 border-surface-700/30',
                        )}>
                          {server.category}
                        </span>
                      </div>
                    </div>
                    {server.homepage && (
                      <a
                        href={server.homepage}
                        target="_blank"
                        rel="noreferrer"
                        className="icon-btn"
                        title="Open docs"
                      >
                        <GlobeIcon size={15} />
                      </a>
                    )}
                  </div>
                  <p className="text-xs text-surface-400 leading-relaxed mb-3 flex-1">{server.description}</p>
                  <div className="rounded-xl bg-surface-950/70 border border-surface-700/25 px-3 py-2.5 font-mono text-[11px] text-surface-300 break-all">
                    {server.command} {server.args.join(' ')}
                  </div>
                  {server.env_vars.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {server.env_vars.map((env) => (
                        <span key={env} className="px-2 py-0.5 rounded-md text-[10px] bg-amber-500/8 text-amber-400/80 border border-amber-500/15 font-mono">
                          {env}
                        </span>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => copyServerConfig(server)}
                    className="mt-3 flex items-center justify-center gap-2 text-xs py-2 rounded-xl bg-surface-700/30 border border-surface-600/20 text-surface-300 hover:bg-surface-700/50 hover:text-surface-100 active:scale-[0.98] transition-all"
                  >
                    <CopyIcon size={13} />
                    Copy config
                    <ArrowRightIcon size={11} className="opacity-0 group-hover:opacity-100 -ml-1 transition-opacity" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}