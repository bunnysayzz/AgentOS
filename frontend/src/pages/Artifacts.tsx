import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArchiveIcon, ArrowLeftIcon, ChevronRightIcon, CodeIcon, FileIcon, ImageIcon, PlusIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { cn } from '@/utils/cn'

interface Artifact { id: string; name: string; content_type: string; size_bytes: number; version: number; checksum?: string; created_at: string }

function contentTypeIcon(ct: string) {
  if (ct.startsWith('image')) return <ImageIcon size={18} />
  if (ct.includes('json') || ct.includes('yaml')) return <CodeIcon size={18} />
  return <FileIcon size={18} />
}

export default function Artifacts() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [showCreate, setShowCreate] = useState(false)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', content_type: 'application/octet-stream', metadata: '' })
  const [filterType, setFilterType] = useState('')

  const { data: artifacts, isLoading } = useQuery({
    queryKey: ['artifacts', wsId, filterType],
    queryFn: () => api.get(`/workspaces/${wsId}/artifacts/`, { params: { content_type: filterType || undefined } }).then((r) => r.data),
    enabled: !!wsId,
  })

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: (d: typeof form) => api.post(`/workspaces/${wsId}/artifacts/`, { name: d.name, content_type: d.content_type, metadata: d.metadata ? JSON.parse(d.metadata) : undefined }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['artifacts', wsId] }); setShowCreate(false); setForm({ name: '', content_type: 'application/octet-stream', metadata: '' }) },
  })

  const list: Artifact[] = Array.isArray(artifacts) ? artifacts : []

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Artifacts</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace to view artifacts</p></div>

  if (detailId) {
    const a = list.find((x) => x.id === detailId)
    if (!a) return <div className="space-y-4"><button onClick={() => setDetailId(null)} className="text-primary-400">&larr; Back</button><p>Not found</p></div>
    return (
      <div className="space-y-6">
        <button onClick={() => setDetailId(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200"><ArrowLeftIcon size={14} />Back</button>
        <div className="flex items-start justify-between">
          <div><h1 className="text-2xl font-bold">{a.name}</h1><p className="text-surface-400 text-sm mt-1">{a.content_type}</p></div>
          <span className="chip">v{a.version}</span>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="card"><p className="text-xs text-surface-500 mb-1">Size</p><p className="font-medium">{a.size_bytes > 1024 ? `${(a.size_bytes / 1024).toFixed(1)} KB` : `${a.size_bytes} B`}</p></div>
          <div className="card"><p className="text-xs text-surface-500 mb-1">Version</p><p className="font-medium">{a.version}</p></div>
          <div className="card"><p className="text-xs text-surface-500 mb-1">Checksum</p><p className="font-mono text-xs truncate">{a.checksum || '—'}</p></div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Artifacts</h1><p className="text-surface-400 text-sm mt-1">{list.length} artifact{list.length !== 1 ? 's' : ''}</p></div>
        <div className="flex items-center gap-3"><WorkspaceSelector /><button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2"><PlusIcon size={16} />New Artifact</button></div>
      </div>

      <div className="flex gap-2 items-center">
        {['', 'image/', 'application/json', 'text/'].map((ct) => (
          <button key={ct} onClick={() => setFilterType(ct)} className={cn('chip cursor-pointer hover:bg-surface-700 transition-colors', filterType === ct && 'bg-primary-500/20 text-primary-400 border-primary-500/30')}>
            {ct || 'All'}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card animate-pulse"><div className="h-5 w-48 bg-surface-800 rounded mb-2" /><div className="h-4 w-32 bg-surface-800 rounded" /></div>)}</div>
      ) : list.length === 0 ? (
        <div className="glass-panel p-12 text-center"><ArchiveIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" /><h3 className="text-lg font-medium text-surface-400">No artifacts yet</h3></div>
      ) : (
        <div className="grid gap-3">{list.map((a) => (
          <div key={a.id} onClick={() => setDetailId(a.id)} className="card flex items-center justify-between group cursor-pointer">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-surface-800 border border-surface-700/50 flex items-center justify-center">{contentTypeIcon(a.content_type)}</div>
              <div><p className="font-medium group-hover:text-primary-400 transition-colors">{a.name}</p><p className="text-xs text-surface-500">{a.content_type} · v{a.version} · {a.size_bytes > 1024 ? `${(a.size_bytes / 1024).toFixed(1)} KB` : `${a.size_bytes} B`}</p></div>
            </div>
            <ChevronRightIcon size={16} className="text-surface-500 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        ))}</div>
      )}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Register Artifact</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label><input type="text" placeholder="my-file.json" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Content Type</label><select value={form.content_type} onChange={(e) => setForm({ ...form, content_type: e.target.value })} className="input-field"><option value="application/octet-stream">Binary</option><option value="application/json">JSON</option><option value="text/plain">Text</option><option value="image/png">PNG Image</option><option value="text/yaml">YAML</option></select></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Metadata (JSON)</label><textarea placeholder='{"key": "value"}' value={form.metadata} onChange={(e) => setForm({ ...form, metadata: e.target.value })} className="input-field min-h-[60px] resize-none font-mono text-sm" rows={2} /></div>
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
