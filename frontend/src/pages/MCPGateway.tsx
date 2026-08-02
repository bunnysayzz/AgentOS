import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CpuIcon, DatabaseIcon, DollarSignIcon, MessageSquareIcon, PhoneIcon, ActivityIcon, ClockIcon, CheckCircleIcon } from '@/components/Icons'
import api from '@/services/api'
import ChatInterface from '@/components/ChatInterface'
import { cn } from '@/utils/cn'

interface Model { id: string; model_name: string; provider: string; input_price: number; output_price: number; is_active: boolean }
interface Call { id: string; model_name: string; provider: string; prompt_tokens: number; completion_tokens: number; cost_usd: number; created_at: string; status: string }

export default function MCPGateway() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'chat' | 'models' | 'costs' | 'calls'>('chat')

  const { data: models } = useQuery({
    queryKey: ['mcp-models'],
    queryFn: () => api.get('/mcp/models').then((r) => r.data),
  })

  const { data: calls } = useQuery({
    queryKey: ['mcp-calls'],
    queryFn: () => api.get('/mcp/calls').then((r) => r.data),
  })

  const { mutate: seedModels } = useMutation({
    mutationFn: () => api.post('/mcp/models/seed').then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['mcp-models'] }); qc.invalidateQueries({ queryKey: ['mcp-costs'] }) },
  })

  const modelList: Model[] = Array.isArray(models) ? models : []
  const callList: Call[] = Array.isArray(calls) ? calls : []

  // Stats
  const totalTokens = callList.reduce((s, c) => s + (c.prompt_tokens || 0) + (c.completion_tokens || 0), 0)
  const totalCost = callList.reduce((s, c) => s + (c.cost_usd || 0), 0)
  const recentCalls = callList.slice(-5).reverse()
  const activeModels = modelList.filter((m) => m.is_active).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">MCP Gateway</h1>
          <p className="text-surface-400 text-sm mt-1">LLM model routing, pricing, and cost tracking</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl bg-surface-800/50 w-fit flex-wrap">
        {(['chat', 'models', 'calls', 'costs'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all',
              tab === t ? 'bg-surface-700 text-white' : 'text-surface-400 hover:text-surface-200',
            )}
          >
            {t === 'chat' && <MessageSquareIcon size={14} className="inline mr-1.5" />}
            {t === 'models' && <CpuIcon size={14} className="inline mr-1.5" />}
            {t === 'calls' && <PhoneIcon size={14} className="inline mr-1.5" />}
            {t === 'costs' && <DollarSignIcon size={14} className="inline mr-1.5" />}
            {t}
          </button>
        ))}
      </div>

      {/* ── CHAT TAB ── */}
      {tab === 'chat' && (
        <ChatInterface
          title="MCP Chat"
          height="600px"
          showProviderSelector={true}
          placeholder="Ask the AI anything..."
        />
      )}

      {/* ── MODELS TAB ── */}
      {tab === 'models' && (
        <div className="grid gap-3">
          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="card">
              <CpuIcon size={18} className="text-primary-400 mb-2" />
              <p className="text-2xl font-bold">{modelList.length}</p>
              <p className="text-xs text-surface-500">Total Models</p>
            </div>
            <div className="card">
              <CheckCircleIcon size={18} className="text-emerald-400 mb-2" />
              <p className="text-2xl font-bold">{activeModels}</p>
              <p className="text-xs text-surface-500">Active</p>
            </div>
            <div className="card">
              <ActivityIcon size={18} className="text-amber-400 mb-2" />
              <p className="text-2xl font-bold">{callList.length}</p>
              <p className="text-xs text-surface-500">Total Calls</p>
            </div>
            <div className="card">
              <DollarSignIcon size={18} className="text-emerald-400 mb-2" />
              <p className="text-2xl font-bold">${totalCost.toFixed(6)}</p>
              <p className="text-xs text-surface-500">Total Cost</p>
            </div>
          </div>

          <div className="flex justify-end mb-2">
            <button onClick={() => seedModels()} className="btn-secondary flex items-center gap-2 text-sm">
              <DatabaseIcon size={14} />Seed Models
            </button>
          </div>
          {modelList.length === 0 ? (
            <div className="glass-panel p-12 text-center">
              <CpuIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
              <h3 className="text-lg font-medium text-surface-400">No models loaded</h3>
              <p className="text-sm text-surface-500 mt-2">Click "Seed Models" to populate with default LLM models</p>
            </div>
          ) : (
            <div className="grid gap-2">
              {modelList.map((m) => (
                <div key={m.id} className="card flex items-center justify-between">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className={cn('w-2 h-2 rounded-full', m.is_active ? 'bg-emerald-400' : 'bg-surface-600')} />
                    <div className="min-w-0">
                      <p className="font-medium truncate">{m.model_name}</p>
                      <p className="text-xs text-surface-500">{m.provider}</p>
                    </div>
                  </div>
                  <div className="text-right text-xs text-surface-400 flex-shrink-0">
                    <div>${m.input_price}/1K in</div>
                    <div>${m.output_price}/1K out</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── CALLS TAB ── */}
      {tab === 'calls' && (
        <div className="grid gap-3">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="card">
              <PhoneIcon size={18} className="text-primary-400 mb-2" />
              <p className="text-2xl font-bold">{callList.length}</p>
              <p className="text-xs text-surface-500">Total Calls</p>
            </div>
            <div className="card">
              <ActivityIcon size={18} className="text-amber-400 mb-2" />
              <p className="text-2xl font-bold">{totalTokens.toLocaleString()}</p>
              <p className="text-xs text-surface-500">Total Tokens</p>
            </div>
            <div className="card">
              <ClockIcon size={18} className="text-emerald-400 mb-2" />
              <p className="text-2xl font-bold">{recentCalls.length > 0 ? recentCalls[0].created_at?.slice(0, 10) : '—'}</p>
              <p className="text-xs text-surface-500">Latest Call</p>
            </div>
          </div>

          {callList.length === 0 ? (
            <div className="glass-panel p-12 text-center">
              <PhoneIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
              <h3 className="text-lg font-medium text-surface-400">No calls yet</h3>
              <p className="text-sm text-surface-500 mt-2">Start a chat or execute an agent to see LLM calls here</p>
            </div>
          ) : (
            <div className="grid gap-2">
              {callList.map((c) => (
                <div key={c.id} className="card flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{c.model_name}</p>
                    <p className="text-xs text-surface-500">{c.provider} · {(c.prompt_tokens || 0) + (c.completion_tokens || 0).toLocaleString()} tokens</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-medium">${c.cost_usd.toFixed(6)}</p>
                    <p className="text-xs text-surface-500">{c.created_at?.slice(0, 10)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── COSTS TAB ── */}
      {tab === 'costs' && (
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="card">
              <DollarSignIcon size={18} className="text-emerald-400 mb-2" />
              <p className="text-3xl font-bold">${totalCost.toFixed(6)}</p>
              <p className="text-xs text-surface-500">Total lifetime cost</p>
            </div>
            <div className="card">
              <ActivityIcon size={18} className="text-amber-400 mb-2" />
              <p className="text-3xl font-bold">{totalTokens.toLocaleString()}</p>
              <p className="text-xs text-surface-500">Total tokens processed</p>
            </div>
          </div>

          {/* Call cost breakdown */}
          {callList.length > 0 && (
            <div className="glass-panel p-5">
              <h3 className="font-medium mb-3">Recent Calls</h3>
              <div className="space-y-2">
                {callList.slice(-10).reverse().map((c) => (
                  <div key={c.id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-surface-800/50">
                    <div className="min-w-0">
                      <p className="text-sm truncate">{c.model_name}</p>
                      <p className="text-xs text-surface-500">{c.provider}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-xs font-medium">${c.cost_usd.toFixed(6)}</p>
                      <p className="text-[10px] text-surface-500">{((c.prompt_tokens || 0) + (c.completion_tokens || 0)).toLocaleString()} tokens</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {callList.length === 0 && (
            <div className="glass-panel p-12 text-center">
              <DollarSignIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
              <h3 className="text-lg font-medium text-surface-400">No cost data yet</h3>
              <p className="text-sm text-surface-500 mt-2">Cost data appears after you make LLM calls through the chat</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
