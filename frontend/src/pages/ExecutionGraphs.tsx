import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ActivityIcon, ClockIcon, DollarSignIcon, GitBranchIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { cn } from '@/utils/cn'

interface Node { id: string; node_name?: string; node_type: string; status: string; duration_ms?: number; cost_usd?: number; prompt_tokens?: number; completion_tokens?: number; error_message?: string; created_at: string }

export default function ExecutionGraphs() {
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [executionId, setExecutionId] = useState('')
  const [loadedExec, setLoadedExec] = useState('')

  const { data: graph, isLoading } = useQuery({
    queryKey: ['execution-graph', wsId, loadedExec],
    queryFn: () => api.get(`/workspaces/${wsId}/executions/${loadedExec}/graph`).then((r) => r.data),
    enabled: !!wsId && !!loadedExec,
  })

  const nodes: Node[] = graph?.nodes || []

  const statusColor = (s: string) => {
    switch (s) {
      case 'completed': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
      case 'failed': return 'text-red-400 bg-red-500/10 border-red-500/20'
      case 'running': return 'text-sky-400 bg-sky-500/10 border-sky-500/20'
      case 'pending': return 'text-surface-400 bg-surface-800 border-surface-700/30'
      default: return 'text-surface-400 bg-surface-800 border-surface-700/30'
    }
  }

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Execution Graphs</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace to view graphs</p></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Execution Graphs</h1><p className="text-surface-400 text-sm mt-1">Node-level execution tracing</p></div>
        <WorkspaceSelector />
      </div>

      <div className="flex gap-2">
        <input type="text" placeholder="Enter execution ID..." value={executionId} onChange={(e) => setExecutionId(e.target.value)} className="input-field flex-1" />
        <button onClick={() => { if (executionId.trim()) setLoadedExec(executionId.trim()) }} disabled={!executionId.trim()} className="btn-primary">Load Graph</button>
      </div>

      {isLoading && <div className="glass-panel p-12 text-center"><div className="w-8 h-8 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin mx-auto" /></div>}

      {graph && !isLoading && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card"><GitBranchIcon size={18} className="text-primary-400 mb-2" /><p className="text-2xl font-bold">{nodes.length}</p><p className="text-xs text-surface-500">Nodes</p></div>
            <div className="card"><ActivityIcon size={18} className={cn('mb-2', graph.total_duration_ms > 0 ? 'text-emerald-400' : 'text-surface-500')} /><p className="text-2xl font-bold">{graph.total_duration_ms}ms</p><p className="text-xs text-surface-500">Total Duration</p></div>
            <div className="card"><DollarSignIcon size={18} className={cn('mb-2', graph.total_cost_usd > 0 ? 'text-emerald-400' : 'text-surface-500')} /><p className="text-2xl font-bold">${graph.total_cost_usd?.toFixed(6) || '0'}</p><p className="text-xs text-surface-500">Total Cost</p></div>
            <div className="card"><ClockIcon size={18} className={cn('mb-2', graph.total_tokens > 0 ? 'text-amber-400' : 'text-surface-500')} /><p className="text-2xl font-bold">{graph.total_tokens?.toLocaleString() || '0'}</p><p className="text-xs text-surface-500">Total Tokens</p></div>
          </div>

          {/* Nodes */}
          <div className="glass-panel p-5">
            <h3 className="font-medium mb-4">Node Timeline</h3>
            <div className="space-y-2">
              {nodes.map((n, i) => (
                <div key={n.id} className={cn('flex items-start gap-4 p-4 rounded-xl border', statusColor(n.status))}>
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-surface-900 text-xs font-bold text-surface-500 flex-shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{n.node_name || n.node_type}</span>
                      <span className="chip text-[10px]">{n.node_type}</span>
                    </div>
                    {n.error_message && <p className="text-xs text-red-400 mt-1">{n.error_message}</p>}
                    <div className="flex items-center gap-3 mt-2 text-xs text-surface-500">
                      <span>Status: {n.status}</span>
                      {n.duration_ms !== null && <span>{n.duration_ms}ms</span>}
                      {n.cost_usd !== null && <span>${n.cost_usd?.toFixed(6)}</span>}
                      {(n.prompt_tokens || n.completion_tokens) && <span>{((n.prompt_tokens || 0) + (n.completion_tokens || 0)).toLocaleString()} tokens</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {loadedExec && !graph && !isLoading && (
        <div className="glass-panel p-12 text-center">
          <GitBranchIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-surface-400">No graph data</h3>
          <p className="text-sm text-surface-500 mt-2">This execution may not have any traced nodes yet</p>
        </div>
      )}
    </div>
  )
}
