import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { KeyIcon, PlusIcon, Trash2Icon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { confirm } from '@/components/ConfirmDialog'

interface Secret { id: string; name: string; slug: string; description?: string; environment?: string; provider?: string; created_at: string }

export default function Secrets() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '', description: '', value: '', environment: '', provider: 'generic' })

  const { data: secrets, isLoading } = useQuery({
    queryKey: ['secrets', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/secrets/`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: (d: typeof form) => api.post(`/workspaces/${wsId}/secrets/`, d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['secrets', wsId] }); setShowCreate(false); setForm({ name: '', slug: '', description: '', value: '', environment: '', provider: 'generic' }) },
  })

  const { mutate: remove } = useMutation({
    mutationFn: (id: string) => api.delete(`/workspaces/${wsId}/secrets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['secrets', wsId] }),
  })

  const list: Secret[] = Array.isArray(secrets) ? secrets : []

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Secrets</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace to view secrets</p></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Secrets</h1><p className="text-surface-400 text-sm mt-1">{list.length} secret{list.length !== 1 ? 's' : ''}</p></div>
        <div className="flex items-center gap-3"><WorkspaceSelector /><button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2"><PlusIcon size={16} />New Secret</button></div>
      </div>
      {isLoading ? (
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card animate-pulse"><div className="h-5 w-48 bg-surface-800 rounded mb-2" /><div className="h-4 w-32 bg-surface-800 rounded" /></div>)}</div>
      ) : list.length === 0 ? (
        <div className="glass-panel p-12 text-center"><KeyIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" /><h3 className="text-lg font-medium text-surface-400">No secrets yet</h3><p className="text-sm text-surface-500 mt-1 mb-4">Store encrypted API keys and credentials</p><button onClick={() => setShowCreate(true)} className="btn-primary">Add Secret</button></div>
      ) : (
        <div className="grid gap-3">{list.map((sec) => (
          <div key={sec.id} className="card flex items-center justify-between group">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/10 flex items-center justify-center"><KeyIcon size={18} className="text-amber-400" /></div>
              <div><p className="font-medium">{sec.name}</p><p className="text-xs text-surface-500">/{sec.slug}{sec.environment ? ` · ${sec.environment}` : ''}</p></div>
            </div>
            <button onClick={() => confirm.danger('Delete Secret?', `Delete "${sec.name}"? This cannot be undone.`, async () => remove(sec.id))} className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-red-500/10 text-surface-500 hover:text-red-400 transition-all">
              <Trash2Icon size={14} />
            </button>
          </div>
        ))}</div>
      )}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Add Secret</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label><input type="text" placeholder="OpenAI API KeyIcon" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Slug</label><input type="text" placeholder="openai-key" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Value <span className="text-red-400">*encrypted at rest</span></label><input type="password" placeholder="sk-..." value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Environment</label><select value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value })} className="input-field"><option value="">Any</option><option value="development">Development</option><option value="staging">Staging</option><option value="production">Production</option></select></div>
              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowCreate(false)} className="btn-secondary flex-1">Cancel</button>
                <button onClick={() => create(form)} disabled={!form.name.trim() || !form.value.trim() || creating} className="btn-primary flex-1 flex items-center justify-center gap-2">
                  {creating ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><PlusIcon size={16} />Add</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
