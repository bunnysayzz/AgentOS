import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftIcon, ChevronRightIcon, CodeIcon, EyeIcon, FileTextIcon, HistoryIcon, PlusIcon, RotateCcwIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import WorkspaceRequired from '@/components/WorkspaceRequired'
import { confirm } from '@/components/ConfirmDialog'
import { cn } from '@/utils/cn'

interface Prompt { id: string; name: string; slug: string; description?: string; current_version: number; created_at: string }
interface Version { id: string; version: number; content: string; commit_message?: string; created_at: string }

export default function Prompts() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [showCreate, setShowCreate] = useState(false)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [viewVersion, setViewVersion] = useState<number | null>(null)
  const [form, setForm] = useState({ name: '', slug: '', description: '', initial_content: '' })

  const { data: prompts, isLoading } = useQuery({
    queryKey: ['prompts', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/prompts`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: versions } = useQuery({
    queryKey: ['prompt-versions', detailId],
    queryFn: () => api.get(`/prompts/${detailId}/versions`).then((r) => r.data),
    enabled: !!detailId,
  })

  const { data: versionContent } = useQuery({
    queryKey: ['prompt-version', detailId, viewVersion],
    queryFn: () => api.get(`/prompts/${detailId}/versions/${viewVersion}`).then((r) => r.data),
    enabled: !!detailId && viewVersion !== null,
  })

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: (d: typeof form) => api.post(`/workspaces/${wsId}/prompts`, d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prompts', wsId] }); setShowCreate(false); setForm({ name: '', slug: '', description: '', initial_content: '' }) },
  })

  const { mutate: createVersion } = useMutation({
    mutationFn: (content: string) => api.post(`/prompts/${detailId}/versions`, { content }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prompt-versions', detailId] }); setViewVersion(null) },
  })

  const { mutate: rollback } = useMutation({
    mutationFn: (version: number) => api.post(`/prompts/${detailId}/rollback/${version}`).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prompt-versions', detailId] }); qc.invalidateQueries({ queryKey: ['prompts', wsId] }) },
  })

  const [renderVars, setRenderVars] = useState('{\n  "role": "expert"\n}')
  const [renderResult, setRenderResult] = useState<string | null>(null)

  const { mutate: renderPrompt, isPending: rendering } = useMutation({
    mutationFn: () => api.post(`/prompts/${detailId}/render`, JSON.parse(renderVars)).then((r) => r.data),
    onSuccess: (data) => setRenderResult(typeof data === 'string' ? data : data.rendered || JSON.stringify(data)),
  })

  const list: Prompt[] = Array.isArray(prompts) ? prompts : []
  const vers: Version[] = Array.isArray(versions) ? versions : []

  if (!wsId) return <WorkspaceRequired title="Prompts" description="Select a workspace to view prompts" />

  if (detailId) {
    const p = list.find((x) => x.id === detailId)
    if (!p) return <div className="space-y-4"><button onClick={() => setDetailId(null)} className="text-primary-400">&larr; Back</button><p>Not found</p></div>

    if (viewVersion !== null && versionContent) {
      return (
        <div className="space-y-6">
          <button onClick={() => setViewVersion(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200"><ArrowLeftIcon size={14} />Back to versions</button>
          <h1 className="text-xl font-bold">v{viewVersion}: {p.name}</h1>
          <div className="glass-panel p-5">
            <pre className="text-sm text-surface-300 whitespace-pre-wrap font-mono">{versionContent.content || '(empty)'}</pre>
          </div>
          <button onClick={() => confirm.warning('Rollback Prompt?',`Rollback to v${viewVersion}? This will create a new version from this point.`,async () => rollback(viewVersion))} className="btn-secondary flex items-center gap-2 text-sm"><RotateCcwIcon size={14} />Rollback to v{viewVersion}</button>
        </div>
      )
    }

    return (
      <div className="space-y-6">
        <button onClick={() => setDetailId(null)} className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200"><ArrowLeftIcon size={14} />Back</button>
        <div className="flex items-start justify-between">
          <div><h1 className="text-2xl font-bold">{p.name}</h1><p className="text-surface-400 text-sm mt-1">{p.description || p.slug}</p></div>
          <span className="chip">v{p.current_version}</span>
        </div>
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2"><HistoryIcon size={16} />Version History</h3>
          </div>
          <div className="space-y-2">
            {vers.map((v) => (
              <div key={v.id} onClick={() => setViewVersion(v.version)} className="flex items-center justify-between py-2 px-3 rounded-xl bg-surface-800/50 hover:bg-surface-800 cursor-pointer transition-all">
                <div className="flex items-center gap-3">
                  <span className={cn('w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold', v.version === p.current_version ? 'bg-primary-500/20 text-primary-400' : 'bg-surface-700 text-surface-400')}>v{v.version}</span>
                  <span className="text-sm">{v.commit_message || `Version ${v.version}`}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={(e) => { e.stopPropagation(); confirm.warning('Rollback?',`Rollback to v${v.version}? This will create a new version.`,async () => rollback(v.version)) }} className="p-1.5 rounded-lg text-surface-500 hover:text-amber-400 hover:bg-amber-500/10 transition-all" title={`Rollback to v${v.version}`}><RotateCcwIcon size={12} /></button>
                  <EyeIcon size={14} className="text-surface-500" />
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => { const c = prompt('Enter new content:'); if (c) createVersion(c) }} className="btn-secondary mt-3 w-full text-sm">+ New Version</button>
        </div>

        {/* Render Prompt */}
        <div className="glass-panel p-5">
          <h3 className="font-medium mb-3 flex items-center gap-2"><CodeIcon size={16} /> Render Prompt</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-surface-400 mb-1">Variables (JSON)</label>
              <textarea
                value={renderVars}
                onChange={(e) => setRenderVars(e.target.value)}
                className="input-field min-h-[80px] resize-none font-mono text-xs"
                rows={4}
              />
            </div>
            <button onClick={() => renderPrompt()} disabled={rendering} className="btn-primary flex items-center gap-2 text-sm">
              {rendering ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <CodeIcon size={14} />}
              Render
            </button>
            {renderResult && (
              <div className="mt-3 p-4 rounded-xl bg-surface-800/50 border border-surface-700/30">
                <p className="text-xs text-surface-400 mb-2">Rendered Output</p>
                <pre className="text-sm text-surface-200 whitespace-pre-wrap font-mono">{renderResult}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Prompt Registry</h1><p className="text-surface-400 text-sm mt-1">{list.length} prompt{list.length !== 1 ? 's' : ''}</p></div>
        <div className="flex items-center gap-3"><WorkspaceSelector /><button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2"><PlusIcon size={16} />New Prompt</button></div>
      </div>
      {isLoading ? (
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="card animate-pulse"><div className="h-5 w-48 bg-surface-800 rounded mb-2" /><div className="h-4 w-32 bg-surface-800 rounded" /></div>)}</div>
      ) : list.length === 0 ? (
        <div className="glass-panel p-12 text-center"><FileTextIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" /><h3 className="text-lg font-medium text-surface-400">No prompts yet</h3><p className="text-sm text-surface-500 mt-1 mb-4">Create your first prompt template</p><button onClick={() => setShowCreate(true)} className="btn-primary">Create Prompt</button></div>
      ) : (
        <div className="grid gap-3">{list.map((p) => (
          <div key={p.id} onClick={() => setDetailId(p.id)} className="card flex items-center justify-between group cursor-pointer">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-amber-600/20 border border-amber-500/10 flex items-center justify-center"><FileTextIcon size={18} className="text-amber-400" /></div>
              <div className="min-w-0"><p className="font-medium truncate group-hover:text-amber-400 transition-colors">{p.name}</p><p className="text-xs text-surface-500">/{p.slug} · v{p.current_version}</p></div>
            </div>
            <ChevronRightIcon size={16} className="text-surface-500 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        ))}</div>
      )}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Create Prompt</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label><input type="text" placeholder="My Prompt" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Slug</label><input type="text" placeholder="my-prompt" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className="input-field" /></div>
              <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Initial Content</label><textarea placeholder="You are a {{role}} assistant..." value={form.initial_content} onChange={(e) => setForm({ ...form, initial_content: e.target.value })} className="input-field min-h-[100px] resize-none font-mono text-sm" rows={4} /></div>
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
