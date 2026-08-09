import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ActivityIcon, ClockIcon, DollarSignIcon, GitBranchIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import EmptyState from '@/components/EmptyState'
import { cn } from '@/utils/cn'

// ─── Shared table primitives ─────────────────────────────────────────
function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <th className={cn('px-4 py-3 text-left text-[10px] font-mono uppercase tracking-wider text-surface-500 font-medium whitespace-nowrap', className)}>{children}</th>
}
function Td({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <td className={cn('px-4 py-3 text-sm whitespace-nowrap', className)}>{children}</td>
}

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

  const statusBadge = (s: string) => cn(
    'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border',
    s === 'completed'
      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
      : s === 'failed'
        ? 'text-red-400 bg-red-500/10 border-red-500/20'
        : s === 'running'
          ? 'text-sky-400 bg-sky-500/10 border-sky-500/20'
          : 'text-surface-400 bg-surface-800 border-surface-700/30',
  )

  // Stagger presets for the node table rows
  const staggerContainer = {
    hidden: {},
    show: { transition: { staggerChildren: 0.04, delayChildren: 0.05 } },
  }
  const staggerRow = {
    hidden: { opacity: 0, x: -8 },
    show: { opacity: 1, x: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const } },
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

          {/* Nodes — data table */}
          <div className="glass-panel overflow-hidden">
            <div className="px-5 pt-5 pb-3">
              <h3 className="font-medium">Node Timeline</h3>
              <p className="text-xs text-surface-500 mt-0.5">{nodes.length} nodes traced for this execution</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px]">
                <thead>
                  <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                    <Th>#</Th>
                    <Th>Node</Th>
                    <Th>Type</Th>
                    <Th>Status</Th>
                    <Th className="text-right">Duration</Th>
                    <Th className="text-right">Cost</Th>
                    <Th className="text-right">Tokens</Th>
                  </tr>
                </thead>
                <motion.tbody
                  className="divide-y divide-white/[0.04]"
                  variants={staggerContainer}
                  initial="hidden"
                  animate="show"
                >
                  {nodes.map((n, i) => (
                    <motion.tr key={n.id} variants={staggerRow} className="group hover:bg-white/[0.03] transition-colors duration-100">
                      <Td className="text-surface-600 font-mono text-xs">{i + 1}</Td>
                      <Td className="max-w-[240px]">
                        <span className="font-medium text-surface-200 truncate block">{n.node_name || n.node_type}</span>
                        {n.error_message && <span className="block text-[11px] text-red-400 truncate mt-0.5" title={n.error_message}>{n.error_message}</span>}
                      </Td>
                      <Td><span className="chip text-[10px]">{n.node_type}</span></Td>
                      <Td><span className={statusBadge(n.status)}>{n.status}</span></Td>
                      <Td className="text-right text-surface-400 tabular-nums">{n.duration_ms != null ? `${n.duration_ms}ms` : '—'}</Td>
                      <Td className="text-right text-surface-400 tabular-nums">{n.cost_usd != null ? `$${n.cost_usd.toFixed(6)}` : '—'}</Td>
                      <Td className="text-right text-surface-400 tabular-nums">
                        {(n.prompt_tokens || n.completion_tokens) ? ((n.prompt_tokens || 0) + (n.completion_tokens || 0)).toLocaleString() : '—'}
                      </Td>
                    </motion.tr>
                  ))}
                </motion.tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {loadedExec && !graph && !isLoading && (
        <EmptyState
          icon={GitBranchIcon}
          title="No graph data"
          description="This execution may not have any traced nodes yet, or the ID doesn't match an execution in this workspace."
        />
      )}
    </div>
  )
}
