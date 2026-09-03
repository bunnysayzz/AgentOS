import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GlobeIcon, PlusIcon, SearchIcon, Trash2Icon, WrenchIcon, ChevronRightIcon, ArrowLeftIcon, CodeIcon, CpuIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import WorkspaceRequired from '@/components/WorkspaceRequired'
import TabBar, { type TabItem } from '@/components/TabBar'
import { confirm } from '@/components/ConfirmDialog'
import { toast } from '@/components/Toast'

interface Tool { id: string; name: string; slug: string; description?: string; tool_type: string; source?: string; config?: any; created_at: string }

const TOOL_TABS: TabItem<'workspace' | 'public'>[] = [
  { id: 'workspace', label: 'Workspace' },
  { id: 'public', label: 'Public', icon: GlobeIcon },
]

function toolTypeIcon(type: string, size = 18) {
  switch (type) {
    case 'webhook': return <GlobeIcon size={size} className="text-sky-400" />
    case 'mcp': return <CpuIcon size={size} className="text-violet-400" />
    case 'builtin': return <CodeIcon size={size} className="text-emerald-400" />
    default: return <WrenchIcon size={size} className="text-amber-400" />
  }
}

export default function Tools() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [showCreate, setShowCreate] = useState(false)
  const [tab, setTab] = useState<'workspace' | 'public'>('workspace')
  const [detailId, setDetailId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({ name: '', slug: '', description: '', tool_type: 'custom', source: '' })

  const { data: workspaceTools, isLoading: wsLoading } = useQuery({
    queryKey: ['tools', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/tools`).then((r) => r.data),
    enabled: !!wsId && tab === 'workspace',
  })

  const { data: publicTools, isLoading: pubLoading } = useQuery({
    queryKey: ['public-tools'],
    queryFn: () => api.get('/tools/public').then((r) => r.data),
    enabled: tab === 'public',
  })

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: (d: typeof form) => api.post(`/workspaces/${wsId}/tools`, d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tools', wsId] }); qc.invalidateQueries({ queryKey: ['dashboard-stats'] }); setShowCreate(false); setForm({ name: '', slug: '', description: '', tool_type: 'custom', source: '' }) },
  })

  const { mutate: removeTool } = useMutation({
    mutationFn: (toolId: string) => api.delete(`/workspaces/${wsId}/tools/${toolId}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tools', wsId] }); qc.invalidateQueries({ queryKey: ['dashboard-stats'] }); toast.success('Tool deleted', 'The tool has been removed.') },
  })

  const allTools: Tool[] = tab === 'workspace'
    ? (Array.isArray(workspaceTools) ? workspaceTools : [])
    : (Array.isArray(publicTools) ? publicTools : [])

  const filtered = allTools.filter((t) =>
    !search || t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.slug.toLowerCase().includes(search.toLowerCase()) ||
    t.tool_type.toLowerCase().includes(search.toLowerCase())
  )
  const isLoading = tab === 'workspace' ? wsLoading : pubLoading

  if (!wsId) return <WorkspaceRequired title="Tools" description="Select a workspace to view tools" />

  // ── Detail View ──
  if (detailId) {
    const tool = allTools.find((t) => t.id === detailId)
    if (!tool) return <div className="space-y-4"><button onClick={() => setDetailId(null)} className="text-primary-400">&larr; Back</button><p>Not found</p></div>
    return (
      <div className="space-y-6">
        <button onClick={() => setDetailId(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200">
          <ArrowLeftIcon size={14} />Back to tools
        </button>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-surface-800 border border-surface-700/50 flex items-center justify-center">
              {toolTypeIcon(tool.tool_type, 24)}
            </div>
            <div>
              <h1 className="text-2xl font-bold">{tool.name}</h1>
              <p className="text-surface-400 text-sm mt-1">/{tool.slug}</p>
            </div>
          </div>
          <span className="chip">{tool.tool_type}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card md:col-span-2">
            <p className="text-xs text-surface-500 mb-1">Description</p>
            <p className="text-sm">{tool.description || 'No description'}</p>
          </div>
          <div className="card">
            <p className="text-xs text-surface-500 mb-1">Type</p>
            <p className="text-sm capitalize font-medium">{tool.tool_type}</p>
            {tool.source && <p className="text-xs text-surface-500 mt-1">Source: {tool.source}</p>}
          </div>
        </div>
        {tool.config && (
          <div className="glass-panel p-5">
            <h3 className="font-medium mb-2">Configuration</h3>
            <pre className="text-xs text-surface-400 font-mono bg-surface-800/50 p-3 rounded-lg overflow-auto max-h-60">{JSON.stringify(tool.config, null, 2)}</pre>
          </div>
        )}
      </div>
    )
  }

  // ── List View ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Tools</h1><p className="text-surface-400 text-sm mt-1">{filtered.length} tool{filtered.length !== 1 ? 's' : ''}</p></div>
        <div className="flex items-center gap-3"><WorkspaceSelector /><button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2"><PlusIcon size={16} />New Tool</button></div>
      </div>

      {/* Tabs + Search */}
      <div className="flex flex-wrap items-center gap-3">
        <TabBar
          tabs={TOOL_TABS}
          active={tab}
          onChange={setTab}
        />
        <div className="relative flex-1 max-w-xs">
          <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
          <input
            type="text"
            placeholder="Search tools..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field pl-9 py-2 text-sm"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card animate-pulse"><div className="h-5 w-48 bg-surface-800 rounded mb-2" /><div className="h-4 w-32 bg-surface-800 rounded" /></div>)}</div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <WrenchIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-surface-400">{search ? 'No matching tools' : 'No tools found'}</h3>
          <p className="text-sm text-surface-500 mt-2 mb-4">
            {search ? `No tools match "${search}". Try a different search.` : 'Create your first tool to extend agent capabilities.'}
          </p>
          {!search && <button onClick={() => setShowCreate(true)} className="btn-primary">Create Tool</button>}
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map((tool) => (
            <div key={tool.id} className="card flex items-center justify-between group cursor-pointer hover:border-surface-600/50 transition-all" onClick={() => setDetailId(tool.id)}>
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-10 h-10 rounded-xl bg-surface-800 border border-surface-700/50 flex items-center justify-center flex-shrink-0">
                  {toolTypeIcon(tool.tool_type)}
                </div>
                <div className="min-w-0">
                  <p className="font-medium truncate group-hover:text-primary-400 transition-colors">{tool.name}</p>
                  <p className="text-xs text-surface-500 truncate">{tool.slug} · {tool.tool_type}{tool.description ? ` · ${tool.description.slice(0, 60)}` : ''}</p>
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => { e.stopPropagation(); confirm.danger('Delete Tool?', `Delete "${tool.name}"? This cannot be undone.`, async () => removeTool(tool.id)) }}
                  className="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                  title="Delete tool"
                >
                  <Trash2Icon size={14} />
                </button>
                <ChevronRightIcon size={16} className="text-surface-500" />
              </div>
            </div>
          ))}
        </div>
      )}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Create Tool</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label><input type="text" placeholder="My Tool" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Slug</label><input type="text" placeholder="my-tool" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Description</label><textarea placeholder="What does this tool do?" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input-field min-h-[60px] resize-none" rows={2} /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Type</label><select value={form.tool_type} onChange={(e) => setForm({ ...form, tool_type: e.target.value })} className="input-field"><option value="custom">Custom</option><option value="builtin">Built-in</option><option value="mcp">MCP</option><option value="webhook">Webhook</option></select></div>
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
