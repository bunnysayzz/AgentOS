import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon, CheckIcon, ChevronRightIcon, PauseIcon, PlayIcon, PlusIcon, StopIcon, WorkflowIcon,
  ActivityIcon, ClockIcon, DollarSignIcon, GitBranchIcon,  AlertTriangleIcon, RefreshCwIcon, EyeIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface WF { id: string; name: string; description?: string; status: string; trigger_type?: string; schedule_cron?: string; created_at: string }

function WebhookPanel({ wsId, workflowId }: { wsId: string; workflowId: string }) {
  const [token, setToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const getToken = useMutation({
    mutationFn: () => api.get(`/workspaces/${wsId}/workflows/${workflowId}/webhook-token`).then((r) => r.data),
    onSuccess: (data: any) => setToken(data.webhook_path || ''),
    onError: (err: any) => toast.error('Webhook token', err?.response?.data?.detail || 'Could not load webhook URL (Admin role required)'),
  })

  const copy = async () => {
    if (!token) return
    const url = `${window.location.origin}${token}`
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium flex items-center gap-2">
            <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-2 py-0.5">WEBHOOK</span>
            Inbound trigger URL
          </p>
          <p className="text-xs text-surface-500 mt-1 break-all font-mono">
            {token ? `${window.location.origin}${token}` : 'Generate a token to get the URL. POST any JSON body to it to fire this workflow.'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {!token && (
            <button onClick={() => getToken.mutate()} disabled={getToken.isPending} className="btn-primary text-xs py-1.5 px-3">
              {getToken.isPending ? 'Generating…' : 'Generate URL'}
            </button>
          )}
          {token && (
            <button onClick={copy} className="btn-secondary text-xs py-1.5 px-3">
              {copied ? '✓ Copied' : 'Copy URL'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

interface ExecNode { id: string; node_name?: string; node_type: string; status: string; duration_ms?: number; cost_usd?: number; prompt_tokens?: number; completion_tokens?: number; error_message?: string; created_at: string }

export default function Workflows() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [showCreate, setShowCreate] = useState(false)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [selectedExecId, setSelectedExecId] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', description: '', trigger_type: 'manual', schedule_cron: '' })

  const { data: workflows, isLoading } = useQuery({
    queryKey: ['workflows', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/workflows/`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: execs } = useQuery({
    queryKey: ['wf-executions', detailId],
    queryFn: () => api.get(`/workspaces/${wsId}/workflows/${detailId}/executions`).then((r) => r.data),
    enabled: !!detailId && !!wsId,
    // Poll while any execution is in flight so background DAG results appear.
    refetchInterval: (query) => {
      const rows: any[] = query.state.data || []
      return rows.some((e: any) => ['pending', 'running', 'awaiting_approval'].includes(e.status)) ? 2000 : false
    },
  })

  const { data: execGraph } = useQuery({
    queryKey: ['wf-execution-graph', wsId, selectedExecId],
    queryFn: () => api.get(`/workspaces/${wsId}/executions/${selectedExecId}/graph`).then((r) => r.data),
    enabled: !!wsId && !!selectedExecId,
    refetchInterval: (query) => {
      const nodes: any[] = (query.state.data as any)?.nodes || []
      return nodes.some((n: any) => ['pending', 'running', 'awaiting_input'].includes(n.status)) ? 2000 : false
    },
  })

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: (d: typeof form) => api.post(`/workspaces/${wsId}/workflows/`, d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['workflows', wsId] }); setShowCreate(false); setForm({ name: '', description: '', trigger_type: 'manual', schedule_cron: '' }) },
  })

  const { mutate: execute } = useMutation({
    mutationFn: (id: string) => api.post(`/workspaces/${wsId}/workflows/${id}/execute`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] }),
  })

  const execMutations = {
    start: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/workflows/${detailId}/executions/${id}/start`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] }) }),
    pause: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/workflows/${detailId}/executions/${id}/pause`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] }) }),
    resume: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/workflows/${detailId}/executions/${id}/resume`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] }) }),
    cancel: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/workflows/${detailId}/executions/${id}/cancel`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] }) }),
    approve: useMutation({ mutationFn: (id: string) => api.post(`/workspaces/${wsId}/workflows/${detailId}/executions/${id}/approve`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] }) }),
  }

  const statusColors: Record<string, string> = {
    completed: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    failed: 'text-red-400 bg-red-500/10 border-red-500/20',
    running: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    pending: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    paused: 'text-surface-400 bg-surface-800 border-surface-700/30',
    awaiting_approval: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  }

  const list: WF[] = Array.isArray(workflows) ? workflows : []
  const execList: any[] = Array.isArray(execs) ? execs : []
  const graphNodes: ExecNode[] = execGraph?.nodes || []

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Workflows</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace to view workflows</p></div>

  // ── Execution Detail View (with DAG) ──
  if (detailId && selectedExecId) {
    const ex = execList.find((e: any) => e.id === selectedExecId)
    if (!ex) return <div className="space-y-4"><button onClick={() => setSelectedExecId(null)} className="text-primary-400">&larr; Back</button><p>Not found</p></div>

    const duration = graphNodes.reduce((s: number, n: ExecNode) => s + (n.duration_ms || 0), 0)
    const cost = graphNodes.reduce((s: number, n: ExecNode) => s + (n.cost_usd || 0), 0)
    const tokens = graphNodes.reduce((s: number, n: ExecNode) => s + (n.prompt_tokens || 0) + (n.completion_tokens || 0), 0)

    return (
      <div className="space-y-6">
        <button onClick={() => setSelectedExecId(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200">
          <ArrowLeftIcon size={14} />Back to executions
        </button>

        {/* Execution header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold">Execution Detail</h1>
            <p className="text-xs text-surface-500 font-mono mt-1">{selectedExecId}</p>
          </div>
          <span className={cn('chip', statusColors[ex.status] || 'text-surface-400')}>{ex.status}</span>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card">
            <GitBranchIcon size={18} className="text-primary-400 mb-2" />
            <p className="text-2xl font-bold">{graphNodes.length}</p>
            <p className="text-xs text-surface-500">Nodes</p>
          </div>
          <div className="card">
            <ActivityIcon size={18} className={cn('mb-2', duration > 0 ? 'text-emerald-400' : 'text-surface-500')} />
            <p className="text-2xl font-bold">{duration}ms</p>
            <p className="text-xs text-surface-500">Duration</p>
          </div>
          <div className="card">
            <DollarSignIcon size={18} className={cn('mb-2', cost > 0 ? 'text-emerald-400' : 'text-surface-500')} />
            <p className="text-2xl font-bold">${cost.toFixed(6)}</p>
            <p className="text-xs text-surface-500">Cost</p>
          </div>
          <div className="card">
            <ClockIcon size={18} className={cn('mb-2', tokens > 0 ? 'text-amber-400' : 'text-surface-500')} />
            <p className="text-2xl font-bold">{tokens.toLocaleString()}</p>
            <p className="text-xs text-surface-500">Tokens</p>
          </div>
        </div>

        {/* DAG visualization - node timeline */}
        <div className="glass-panel p-5">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <GitBranchIcon size={16} className="text-primary-400" />
            Execution Graph
          </h3>
          {graphNodes.length === 0 ? (
            <p className="text-sm text-surface-500 py-4 text-center">No graph data available for this execution yet</p>
          ) : (
            <div className="relative">
              {/* Connecting line */}
              <div className="absolute left-[19px] top-0 bottom-0 w-0.5 bg-surface-700/50" />
              <div className="space-y-4">
                {graphNodes.map((n, i) => (
                  <div key={n.id} className="relative flex items-start gap-4">
                    {/* Node number circle */}
                    <div className={cn(
                      'relative z-10 w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold flex-shrink-0 border-2',
                      n.status === 'completed' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                      n.status === 'failed' ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                      n.status === 'running' ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' :
                      'bg-surface-800 border-surface-700/30 text-surface-500'
                    )}>
                      {n.status === 'completed' ? <CheckIcon size={14} /> :
                       n.status === 'failed' ? <AlertTriangleIcon size={14} /> :
                       n.status === 'running' ? <div className="w-3 h-3 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" /> :
                       i + 1}
                    </div>
                    {/* Node content */}
                    <div className={cn(
                      'flex-1 p-4 rounded-xl border',
                      n.status === 'failed' ? 'bg-red-500/5 border-red-500/10' :
                      n.status === 'completed' ? 'bg-surface-800/50 border-surface-700/30' :
                      'bg-surface-800/50 border-surface-700/30'
                    )}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">{n.node_name || n.node_type}</span>
                        <span className="chip text-[10px]">{n.node_type}</span>
                      </div>
                      {n.error_message && (
                        <div className="flex items-start gap-2 mt-2 p-2 rounded-lg bg-red-500/5 border border-red-500/10">
                          <AlertTriangleIcon size={12} className="text-red-400 flex-shrink-0 mt-0.5" />
                          <p className="text-xs text-red-300">{n.error_message}</p>
                        </div>
                      )}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-surface-500">
                        {n.duration_ms != null && <span><ClockIcon size={10} className="inline mr-1" />{n.duration_ms}ms</span>}
                        {n.cost_usd != null && <span><DollarSignIcon size={10} className="inline mr-1" />${n.cost_usd.toFixed(6)}</span>}
                        {(n.prompt_tokens || n.completion_tokens) && <span>Tokens: {((n.prompt_tokens || 0) + (n.completion_tokens || 0)).toLocaleString()}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Workflow Detail View (with executions list) ──
  if (detailId) {
    const wf = list.find((w) => w.id === detailId)
    if (!wf) return <div className="space-y-4"><button onClick={() => setDetailId(null)} className="text-primary-400">&larr; Back</button><p>Not found</p></div>

    // Compute aggregate exec stats
    const completedCount = execList.filter((e: any) => e.status === 'completed').length
    const failedCount = execList.filter((e: any) => e.status === 'failed').length
    const totalDuration = execList.reduce((s: number, e: any) => s + (e.duration_ms || 0), 0)

    return (
      <div className="space-y-6">
        <button onClick={() => setDetailId(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200">
          <ArrowLeftIcon size={14} />Back to workflows
        </button>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{wf.name}</h1>
            <p className="text-surface-400 text-sm mt-1">{wf.description || 'No description'}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('chip', wf.status === 'active' ? 'text-emerald-400 bg-emerald-500/10' : 'text-surface-400')}>{wf.status}</span>
            <span className="chip text-xs">{wf.trigger_type || 'manual'}</span>
          </div>
        </div>

        {wf.trigger_type === 'webhook' && (
          <WebhookPanel wsId={wsId} workflowId={detailId} />
        )}
        {wf.trigger_type === 'schedule' && (
          <div className="glass-panel p-4 text-sm flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-2 py-0.5">SCHEDULE</span>
            <span className="text-surface-500">Cron:</span>
            <code className="font-mono text-primary-400">{wf.schedule_cron || '—'}</code>
            <span className="text-xs text-surface-500">runs while the service is online (checked every 60s)</span>
          </div>
        )}

        {/* Execution stats */}
        {execList.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card">
              <ActivityIcon size={18} className="text-primary-400 mb-2" />
              <p className="text-2xl font-bold">{execList.length}</p>
              <p className="text-xs text-surface-500">Total Executions</p>
            </div>
            <div className="card">
              <CheckIcon size={18} className="text-emerald-400 mb-2" />
              <p className="text-2xl font-bold">{completedCount}</p>
              <p className="text-xs text-surface-500">Completed</p>
            </div>
            <div className="card">
              <AlertTriangleIcon size={18} className={failedCount > 0 ? 'text-red-400 mb-2' : 'text-surface-500 mb-2'} />
              <p className="text-2xl font-bold">{failedCount}</p>
              <p className="text-xs text-surface-500">Failed</p>
            </div>
            <div className="card">
              <ClockIcon size={18} className="text-amber-400 mb-2" />
              <p className="text-2xl font-bold">{totalDuration}ms</p>
              <p className="text-xs text-surface-500">Total Duration</p>
            </div>
          </div>
        )}

        {/* Executions list */}
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2"><ActivityIcon size={16} />Executions</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => qc.invalidateQueries({ queryKey: ['wf-executions', detailId] })}
                className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all"
                title="Refresh"
              >
                <RefreshCwIcon size={14} />
              </button>
              <button onClick={() => execute(wf.id)} className="btn-primary flex items-center gap-2 text-sm py-1.5 px-3">
                <PlayIcon size={14} />Execute
              </button>
            </div>
          </div>
          {execList.length === 0 ? (
            <div className="py-8 text-center">
              <WorkflowIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">No executions yet. Click "Execute" to start one.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {execList.map((ex: any) => (
                <div
                  key={ex.id}
                  onClick={() => setSelectedExecId(ex.id)}
                  className="flex items-center justify-between py-3 px-4 rounded-xl bg-surface-800/50 hover:bg-surface-800 cursor-pointer transition-all border border-transparent hover:border-surface-700/30 group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={cn('chip text-xs capitalize flex-shrink-0', statusColors[ex.status] || 'text-surface-400')}>{ex.status}</span>
                    <span className="text-xs text-surface-500 font-mono truncate hidden sm:inline">{ex.id.slice(0, 12)}...</span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <div className="text-right text-xs text-surface-500 hidden sm:block">
                      {ex.created_at?.slice(0, 10)}
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedExecId(ex.id) }}
                        className="p-1.5 rounded-lg text-surface-500 hover:text-primary-400 hover:bg-primary-500/10 transition-all"
                        title="View graph"
                      >
                        <EyeIcon size={12} />
                      </button>
                      {ex.status === 'pending' && (
                        <button onClick={(e) => { e.stopPropagation(); execMutations.start.mutate(ex.id) }} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all" title="Start">
                          <PlayIcon size={12} />
                        </button>
                      )}
                      {ex.status === 'running' && (
                        <>
                          <button onClick={(e) => { e.stopPropagation(); execMutations.pause.mutate(ex.id) }} className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-all" title="Pause">
                            <PauseIcon />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); execMutations.cancel.mutate(ex.id) }} className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all" title="Cancel">
                            <StopIcon />
                          </button>
                        </>
                      )}
                      {ex.status === 'paused' && (
                        <button onClick={(e) => { e.stopPropagation(); execMutations.resume.mutate(ex.id) }} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all" title="Resume">
                          <PlayIcon size={12} />
                        </button>
                      )}
                      {ex.status === 'awaiting_approval' && (
                        <button onClick={(e) => { e.stopPropagation(); execMutations.approve.mutate(ex.id) }} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all" title="Approve">
                          <CheckIcon size={12} />
                        </button>
                      )}
                    </div>
                    <ChevronRightIcon size={14} className="text-surface-600" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Workflow List View ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Workflows</h1>
          <p className="text-surface-400 text-sm mt-1">{list.length} workflow{list.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2"><PlusIcon size={16} />New Workflow</button>
        </div>
      </div>
      {isLoading ? (
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card animate-pulse"><div className="h-5 w-48 bg-surface-800 rounded mb-2" /><div className="h-4 w-32 bg-surface-800 rounded" /></div>)}</div>
      ) : list.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <WorkflowIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-surface-400">No workflows yet</h3>
          <p className="text-sm text-surface-500 mt-1 mb-4">Create your first workflow to automate AI agent tasks</p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">Create Workflow</button>
        </div>
      ) : (
        <div className="grid gap-3">
          {list.map((wf) => (
            <div key={wf.id} onClick={() => setDetailId(wf.id)} className="card flex items-center justify-between group cursor-pointer hover:border-surface-600/50 transition-all duration-200">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-violet-600/20 border border-violet-500/10 flex items-center justify-center">
                  <WorkflowIcon size={18} className="text-violet-400" />
                </div>
                <div>
                  <p className="font-medium group-hover:text-violet-400 transition-colors">{wf.name}</p>
                  <p className="text-sm text-surface-500">{wf.trigger_type || 'manual'} · {wf.status} · {wf.created_at?.slice(0, 10)}</p>
                </div>
              </div>
              <ChevronRightIcon size={16} className="text-surface-500 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          ))}
        </div>
      )}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Create Workflow</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label><input type="text" placeholder="My Workflow" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Description</label><textarea placeholder="What does this workflow do?" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input-field min-h-[60px] resize-none" rows={2} /></div>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Trigger</label>
                <select value={form.trigger_type} onChange={(e) => setForm({ ...form, trigger_type: e.target.value })} className="input-field">
                  <option value="manual">Manual | run from this page</option>
                  <option value="webhook">Webhook | fire via HTTP POST</option>
                  <option value="schedule">Schedule | run on a cron</option>
                </select>
              </div>
              {form.trigger_type === 'schedule' && (
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-1.5">Cron Expression</label>
                  <input type="text" placeholder="0 8 * * *" value={form.schedule_cron} onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })} className="input-field font-mono" />
                  <p className="text-xs text-surface-500 mt-1">5 fields: minute hour day-of-month month day-of-week (UTC)</p>
                </div>
              )}
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
