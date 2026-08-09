import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GlobeIcon, LockIcon, PlusIcon, RocketIcon, SettingsIcon, UsersIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'

interface Workspace {
  id: string
  name: string
  slug: string
  description?: string
  is_personal: boolean
  role?: string
  created_at: string
}

export default function Workspaces() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const setSelectedWorkspace = useWorkspaceStore((s) => s.setSelectedWorkspace)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', description: '' })

  const { mutate: seedDemo, isPending: seeding } = useMutation({
    mutationFn: () => api.post('/demo/seed').then((r) => r.data),
    onSuccess: (data: { id: string; name: string }) => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      for (const key of ['agents', 'workflows', 'prompts', 'tools', 'memory', 'secrets', 'artifacts']) {
        queryClient.invalidateQueries({ queryKey: [key, data.id] })
        queryClient.invalidateQueries({ queryKey: [key] })
      }
      setSelectedWorkspace(data.id, data.name)
      navigate(`/workspaces/${data.id}`)
    },
  })

  const { data: workspaces, isLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.get('/workspaces/').then((r) => r.data),
  })

  const { mutate: createWorkspace, isPending: creating } = useMutation({
    mutationFn: (data: { name: string; description: string }) =>
      api.post('/workspaces/', data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      setShowCreate(false)
      setForm({ name: '', description: '' })
    },
  })

  const list: Workspace[] = Array.isArray(workspaces) ? workspaces : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Workspaces</h1>
          <p className="text-surface-400 text-sm mt-1">
            {list.length} workspace{list.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <PlusIcon size={16} />
          New Workspace
        </button>
      </div>

      {/* Workspace list */}
      <div className="grid gap-3">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-5 w-48 bg-surface-800 rounded mb-2" />
              <div className="h-4 w-72 bg-surface-800 rounded" />
            </div>
          ))
        ) : list.length === 0 ? (
          <div className="glass-panel p-12 text-center">
            <GlobeIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-surface-400">No workspaces yet</h3>
            <p className="text-sm text-surface-500 mt-1 mb-4">Create your first workspace — or load a pre-built demo to explore AgentOS in action.</p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={() => seedDemo()}
                disabled={seeding}
                className="btn-primary flex items-center gap-2"
              >
                {seeding ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <RocketIcon size={16} />
                )}
                {seeding ? 'Loading demo…' : 'Load demo workspace'}
              </button>
              <button onClick={() => setShowCreate(true)} className="btn-secondary flex items-center gap-2">
                <PlusIcon size={16} />
                Create Workspace
              </button>
            </div>
          </div>
        ) : (
          list.map((ws) => (
            <Link
              key={ws.id}
              to={`/workspaces/${ws.id}`}
              className="card flex items-center justify-between group"
            >
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500/20 to-primary-600/20 border border-primary-500/10 flex items-center justify-center flex-shrink-0">
                  {ws.is_personal ? <LockIcon size={18} className="text-primary-400" /> : <UsersIcon size={18} className="text-primary-400" />}
                </div>
                <div className="min-w-0">
                  <p className="font-medium truncate group-hover:text-primary-400 transition-colors">
                    {ws.name}
                  </p>
                  <p className="text-sm text-surface-500 truncate">
                    {ws.description || `/${ws.slug}`}
                    {ws.role && (
                      <span className="ml-2 chip">
                        {ws.role.charAt(0).toUpperCase() + ws.role.slice(1)}
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-700 text-surface-500 hover:text-surface-300 transition-all">
                  <SettingsIcon size={15} />
                </span>
              </div>
            </Link>
          ))
        )}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4">Create Workspace</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label>
                <input
                  type="text"
                  placeholder="My Workspace"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="input-field"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Description</label>
                <textarea
                  placeholder="What's this workspace for?"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input-field min-h-[80px] resize-none"
                  rows={3}
                />
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setShowCreate(false)}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={() => createWorkspace(form)}
                  disabled={!form.name.trim() || creating}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  {creating ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <PlusIcon size={16} />
                  )}
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
