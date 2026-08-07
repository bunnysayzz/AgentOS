import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ActivityIcon, ArrowLeftIcon, BotIcon, ChevronRightIcon, GlobeIcon, MessageSquareIcon,
  PauseIcon, PlayIcon, PlusIcon, StopIcon, WrenchIcon, KeyIcon,
  Trash2Icon, CheckIcon, XIcon, RefreshCwIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import ChatInterface from '@/components/ChatInterface'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface Agent {
  id: string; name: string; description?: string; system_prompt?: string;
  status: string; model_name: string; model_provider?: string;
  tool_ids?: string[]; config?: Record<string, any>; created_at: string;
  published?: boolean
}

interface Tool {
  id: string; name: string; slug: string; tool_type: string; description?: string
}

export default function Agents() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [showCreate, setShowCreate] = useState(false)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', description: '', system_prompt: '', model_name: 'gpt-4o' })
  const [agentDetailTab, setAgentDetailTab] = useState<'chat' | 'executions' | 'tools'>('chat')

  const { data: agents, isLoading } = useQuery({
    queryKey: ['agents', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/agents/`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: executions } = useQuery({
    queryKey: ['agent-executions', detailId],
    queryFn: () => api.get(`/workspaces/${wsId}/agents/${detailId}/executions`).then((r) => r.data),
    enabled: !!detailId && !!wsId,
    // Poll while any execution is still in flight so the background engine's
    // result (output/tokens/status) shows up automatically.
    refetchInterval: (query) => {
      const rows: any[] = query.state.data || []
      return rows.some((e: any) => ['pending', 'running', 'paused'].includes(e.status)) ? 2000 : false
    },
  })

  // ── Available tools for binding ──
  const { data: availableTools } = useQuery({
    queryKey: ['tools', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/tools`).then((r) => r.data),
    enabled: !!wsId,
  })

  // ── Available secrets for injection ──
  const { data: availableSecrets } = useQuery({
    queryKey: ['secrets', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/secrets/`).then((r) => r.data),
    enabled: !!wsId,
  })

  // ── Gallery publish / unpublish ──
  const { mutate: togglePublish } = useMutation({
    mutationFn: ({ id, publish }: { id: string; publish: boolean }) =>
      (publish ? api.post : api.delete)(`/workspaces/${wsId}/agents/${id}/publish`).then((r) => r.data),
    onSuccess: (_data, { publish }) => {
      qc.invalidateQueries({ queryKey: ['agents', wsId] })
      toast.success('Gallery updated', publish
        ? 'The agent was published to the community gallery.'
        : 'The agent was removed from the community gallery.')
    },
    onError: (err: any) =>
      toast.error('Could not update gallery', err?.response?.data?.detail || 'Failed to update the gallery.'),
  })

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: (d: typeof form) => api.post(`/workspaces/${wsId}/agents/`, d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents', wsId] }); setShowCreate(false); setForm({ name: '', description: '', system_prompt: '', model_name: 'gpt-4o' }) },
  })

  const [executeError, setExecuteError] = useState<string | null>(null)

  const { mutate: execute } = useMutation({
    mutationFn: (id: string) => api.post(`/workspaces/${wsId}/agents/${id}/execute`).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agent-executions', detailId] }); setExecuteError(null) },
    onError: (err: any) => setExecuteError(err.response?.data?.detail || 'Failed to execute agent'),
  })

  const execMutations = {
    start: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/agents/${detailId}/executions/${id}/start`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-executions', detailId] }) }),
    pause: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/agents/${detailId}/executions/${id}/pause`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-executions', detailId] }) }),
    resume: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/agents/${detailId}/executions/${id}/resume`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-executions', detailId] }) }),
    cancel: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/agents/${detailId}/executions/${id}/cancel`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-executions', detailId] }) }),
  }

  // ── Tool binding mutation ──
  const { mutate: updateAgentTools } = useMutation({
    mutationFn: ({ agentId, tool_ids }: { agentId: string; tool_ids: string[] }) =>
      api.patch(`/workspaces/${wsId}/agents/${agentId}`, { tool_ids }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents', wsId] }); toast.success('Tools updated', 'Agent tools have been updated.') },
    onError: (err: any) => toast.error('Failed to update tools', err?.response?.data?.detail),
  })

  // ── Secret injection mutation ──
  const { mutate: injectSecret } = useMutation({
    mutationFn: ({ agentId, secret_id }: { agentId: string; secret_id: string }) => {
      const agent = list.find((a) => a.id === agentId)
      const injectedSecrets = agent?.config?.injected_secrets || []
      return api.patch(`/workspaces/${wsId}/agents/${agentId}`, {
        config: { ...agent?.config, injected_secrets: [...injectedSecrets, secret_id] }
      }).then((r) => r.data)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents', wsId] }); toast.success('Secret injected', 'Secret has been injected into the agent.') },
    onError: (err: any) => toast.error('Failed to inject secret', err?.response?.data?.detail),
  })

  const { mutate: removeInjectedSecret } = useMutation({
    mutationFn: ({ agentId, secret_id }: { agentId: string; secret_id: string }) => {
      const agent = list.find((a) => a.id === agentId)
      const injectedSecrets = agent?.config?.injected_secrets || []
      return api.patch(`/workspaces/${wsId}/agents/${agentId}`, {
        config: { ...agent?.config, injected_secrets: injectedSecrets.filter((s: string) => s !== secret_id) }
      }).then((r) => r.data)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents', wsId] }); toast.success('Secret removed', 'Secret has been removed from the agent.') },
  })

  const list: Agent[] = Array.isArray(agents) ? agents : []
  const execList: any[] = Array.isArray(executions) ? executions : []
  const toolsList: Tool[] = Array.isArray(availableTools) ? availableTools : []
  const secretsList: any[] = Array.isArray(availableSecrets) ? availableSecrets : []

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Agents</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace to view agents</p></div>

  // ── Agent Detail View ──
  if (detailId) {
    const agent = list.find((a) => a.id === detailId)
    if (!agent) return <div className="space-y-4"><button onClick={() => setDetailId(null)} className="text-primary-400">&larr; Back</button><p>Not found</p></div>

    const agentToolIds = agent.tool_ids || []
    const assignedTools = toolsList.filter((t) => agentToolIds.includes(t.id))
    const unassignedTools = toolsList.filter((t) => !agentToolIds.includes(t.id))

    const injectedSecretIds: string[] = agent.config?.injected_secrets || []
    const injectedSecrets = secretsList.filter((s) => injectedSecretIds.includes(s.id))
    const unassignedSecrets = secretsList.filter((s) => !injectedSecretIds.includes(s.id))

    return (
      <div className="space-y-6">
        <button onClick={() => setDetailId(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200 transition-colors">
          <ArrowLeftIcon size={14} />Back to agents
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{agent.name}</h1>
            <p className="text-surface-400 text-sm mt-1">{agent.description || 'No description'}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('chip', agent.status === 'active' ? 'text-emerald-400 bg-emerald-500/10' : 'text-surface-400')}>{agent.status}</span>
            <span className="chip">{agent.model_name}</span>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-1 p-1 rounded-xl bg-surface-800/50 w-fit flex-wrap">
          {(['chat', 'executions', 'tools'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setAgentDetailTab(tab)}
              className={cn('px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all', agentDetailTab === tab ? 'bg-surface-700 text-white' : 'text-surface-400 hover:text-surface-200')}
            >
              {tab === 'chat' && <MessageSquareIcon size={14} className="inline mr-1.5" />}
              {tab === 'executions' && <ActivityIcon size={14} className="inline mr-1.5" />}
              {tab === 'tools' && <WrenchIcon size={14} className="inline mr-1.5" />}
              {tab}
            </button>
          ))}
        </div>

        {/* ── Chat Tab ── */}
        {agentDetailTab === 'chat' && (
          <ChatInterface
            systemPrompt={agent.system_prompt}
            defaultModel={agent.model_name || 'gpt-4o-mini'}
            workspaceId={wsId!}
            title={agent.name}
            height="500px"
          />
        )}

        {/* ── Executions Tab ── */}
        {agentDetailTab === 'executions' && (
          <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium">Execution History</h3>
              <div className="flex items-center gap-2">
                <button onClick={() => qc.invalidateQueries({ queryKey: ['agent-executions', detailId] })}
                  className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all" title="Refresh">
                  <RefreshCwIcon size={14} />
                </button>
                <button onClick={() => execute(agent.id)} className="btn-primary flex items-center gap-2 text-sm py-1.5 px-3">
                  <PlayIcon size={14} />Execute
                </button>
              </div>
            </div>
            {executeError && (
              <div className="mb-3 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-300">
                {executeError}
              </div>
            )}
            {execList.length === 0 ? (
              <div className="py-8 text-center">
                <BotIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
                <p className="text-surface-500 text-sm">No executions yet. Click "Execute" to start one.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {execList.map((ex: any) => (
                  <div key={ex.id} className="py-2 px-3 rounded-xl bg-surface-800/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <ActivityIcon size={14} className={cn(ex.status === 'completed' ? 'text-emerald-400' : ex.status === 'failed' ? 'text-red-400' : 'text-amber-400')} />
                        <span className="text-sm capitalize">{ex.status}</span>
                        {ex.total_tokens != null && (
                          <span className="text-xs text-surface-500">{ex.total_tokens} tokens · ${Number(ex.cost_usd || 0).toFixed(5)}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-surface-500">{ex.created_at?.slice(0, 10)}</span>
                        {ex.status === 'pending' && (
                          <button onClick={() => execMutations.start.mutate(ex.id)} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all" title="Start"><PlayIcon size={12} /></button>
                        )}
                        {ex.status === 'running' && (
                          <>
                            <button onClick={() => execMutations.pause.mutate(ex.id)} className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-all" title="Pause"><PauseIcon /></button>
                            <button onClick={() => execMutations.cancel.mutate(ex.id)} className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all" title="Cancel"><StopIcon /></button>
                          </>
                        )}
                        {ex.status === 'paused' && (
                          <button onClick={() => execMutations.resume.mutate(ex.id)} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all" title="Resume"><PlayIcon size={12} /></button>
                        )}
                      </div>
                    </div>
                    {(ex.status === 'completed' || ex.status === 'failed') && (
                      <div className="mt-2 pl-7">
                        {ex.error_message ? (
                          <p className="text-xs text-red-300/90 bg-red-500/5 border border-red-500/10 rounded-lg p-2 break-words">{ex.error_message}</p>
                        ) : ex.output_data?.response ? (
                          <p className="text-xs text-surface-300 bg-surface-900/40 border border-surface-700/20 rounded-lg p-2 break-words whitespace-pre-wrap">{String(ex.output_data.response).slice(0, 600)}</p>
                        ) : null}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Tools & Secrets Tab ── */}
        {agentDetailTab === 'tools' && (
          <div className="space-y-6">
            {/* ── Tool Binding ── */}
            <div className="glass-panel p-5">
              <h3 className="font-medium mb-3 flex items-center gap-2">
                <WrenchIcon size={16} className="text-primary-400" />
                Assigned Tools ({assignedTools.length})
              </h3>
              {assignedTools.length === 0 && unassignedTools.length === 0 && (
                <p className="text-sm text-surface-500 py-3">No tools available. Create tools in the Tools page first.</p>
              )}
              {assignedTools.length === 0 && unassignedTools.length > 0 && (
                <p className="text-sm text-surface-500 py-3">No tools assigned. Select tools below to assign them.</p>
              )}
              {assignedTools.length > 0 && (
                <div className="space-y-2 mb-4">
                  {assignedTools.map((tool) => (
                    <div key={tool.id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-primary-500/5 border border-primary-500/10">
                      <div className="flex items-center gap-3">
                        <CheckIcon size={14} className="text-emerald-400" />
                        <span className="text-sm font-medium">{tool.name}</span>
                        <span className="chip text-[10px]">{tool.tool_type}</span>
                      </div>
                      <button
                        onClick={() =>            updateAgentTools({
                          agentId: agent.id,
                          tool_ids: agentToolIds.filter((id) => id !== tool.id)
                        })}
                        className="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                        title="Remove tool"
                      >
                        <XIcon size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {unassignedTools.length > 0 && (
                <>
                  <p className="text-xs text-surface-500 mb-2">Available tools | click to assign:</p>
                  <div className="flex flex-wrap gap-2">
                    {unassignedTools.map((tool) => (
                      <button
                        key={tool.id}
                        onClick={() => updateAgentTools({
                          agentId: agent.id,
                          tool_ids: [...agentToolIds, tool.id]
                        })}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 border border-surface-700/30 hover:bg-surface-700 hover:border-primary-500/30 transition-all text-xs"
                      >
                        <PlusIcon size={10} className="text-primary-400" />
                        {tool.name}
                        <span className="text-surface-500">({tool.tool_type})</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* ── Secret Injection ── */}
            <div className="glass-panel p-5">
              <h3 className="font-medium mb-3 flex items-center gap-2">
                <KeyIcon size={16} className="text-amber-400" />
                Injected Secrets ({injectedSecrets.length})
              </h3>
              {injectedSecrets.length === 0 && unassignedSecrets.length === 0 && (
                <p className="text-sm text-surface-500 py-3">No secrets available. Create secrets in the Secrets page first.</p>
              )}
              {injectedSecrets.length === 0 && unassignedSecrets.length > 0 && (
                <p className="text-sm text-surface-500 py-3">No secrets injected. Click a secret below to inject it into this agent.</p>
              )}
              {injectedSecrets.length > 0 && (
                <div className="space-y-2 mb-4">
                  {injectedSecrets.map((sec: any) => (
                    <div key={sec.id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-amber-500/5 border border-amber-500/10">
                      <div className="flex items-center gap-3">
                        <KeyIcon size={14} className="text-amber-400" />
                        <span className="text-sm font-medium">{sec.name}</span>
                        <span className="chip text-[10px]">{sec.environment || 'any'}</span>
                      </div>
                      <button
                        onClick={() => removeInjectedSecret({ agentId: agent.id, secret_id: sec.id })}
                        className="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                        title="Remove secret"
                      >
                        <Trash2Icon size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {unassignedSecrets.length > 0 && (
                <>
                  <p className="text-xs text-surface-500 mb-2">Available secrets | click to inject:</p>
                  <div className="flex flex-wrap gap-2">
                    {unassignedSecrets.map((sec: any) => (
                      <button
                        key={sec.id}
                        onClick={() => injectSecret({ agentId: agent.id, secret_id: sec.id })}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800 border border-surface-700/30 hover:bg-surface-700 hover:border-amber-500/30 transition-all text-xs"
                      >
                        <PlusIcon size={10} className="text-amber-400" />
                        {sec.name}
                        <span className="text-surface-500">/{sec.slug}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Agent List View ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-surface-400 text-sm mt-1">{list.length} agent{list.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2"><PlusIcon size={16} />New Agent</button>
        </div>
      </div>
      {isLoading ? (
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card animate-pulse"><div className="h-5 w-48 bg-surface-800 rounded mb-2" /><div className="h-4 w-32 bg-surface-800 rounded" /></div>)}</div>
      ) : list.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <BotIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-surface-400">No agents yet</h3>
          <p className="text-sm text-surface-500 mt-1 mb-4">Create your first AI agent</p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">Create Agent</button>
        </div>
      ) : (
        <div className="grid gap-3">
          {list.map((agent) => (
            <div key={agent.id} onClick={() => { setDetailId(agent.id); setAgentDetailTab('chat') }} className="card flex items-center justify-between group cursor-pointer hover:border-surface-600/50 transition-all duration-200">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-600/20 border border-emerald-500/10 flex items-center justify-center">
                  <BotIcon size={18} className="text-emerald-400" />
                </div>
                <div>
                  <p className="font-medium group-hover:text-emerald-400 transition-colors">{agent.name}</p>
                  <p className="text-sm text-surface-500">{agent.model_name} · {agent.status}{agent.tool_ids?.length ? ` · ${agent.tool_ids.length} tools` : ''}{agent.published ? ' · published' : ''}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); togglePublish({ id: agent.id, publish: !agent.published }) }}
                  className={cn(
                    'p-2 rounded-lg transition-all',
                    agent.published
                      ? 'text-primary-300 bg-primary-500/10 border border-primary-500/25'
                      : 'text-surface-500 hover:text-primary-400 hover:bg-surface-800 border border-transparent',
                  )}
                  title={agent.published ? 'Unpublish from gallery' : 'Publish to community gallery'}
                >
                  <GlobeIcon size={15} />
                </button>
                <ChevronRightIcon size={16} className="text-surface-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
          ))}
        </div>
      )}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Create Agent</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label><input type="text" placeholder="My Agent" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Description</label><textarea placeholder="What does this agent do?" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input-field min-h-[60px] resize-none" rows={2} /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">System Prompt</label><textarea placeholder="You are a helpful assistant..." value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} className="input-field min-h-[80px] resize-none font-mono text-sm" rows={3} /></div>
              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowCreate(false)} className="btn-secondary flex-1">Cancel</button>
                <button onClick={() => create(form)} disabled={!form.name.trim() || creating} className="btn-primary flex-1 flex items-center justify-center gap-2">
                  {creating ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><PlusIcon size={16} />Create</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
