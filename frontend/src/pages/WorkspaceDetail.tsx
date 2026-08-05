import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ActivityIcon, ArchiveIcon, ArrowLeftIcon, BotIcon, BrainIcon, FileTextIcon, KeyIcon, PlusIcon, SettingsIcon, UserCogIcon, UserMinusIcon, UsersIcon, WorkflowIcon, WrenchIcon } from '@/components/Icons'
import api from '@/services/api'
import { confirm } from '@/components/ConfirmDialog'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'
import { useWorkspaceStore } from '@/stores/workspaceStore'

const tabs = [
  { label: 'Overview', key: 'overview', icon: SettingsIcon },
  { label: 'Agents', key: 'agents', icon: BotIcon, path: '/agents' },
  { label: 'Workflows', key: 'workflows', icon: WorkflowIcon, path: '/workflows' },
  { label: 'Memory', key: 'memory', icon: BrainIcon, path: '/memory' },
  { label: 'Tools', key: 'tools', icon: WrenchIcon, path: '/tools' },
  { label: 'Prompts', key: 'prompts', icon: FileTextIcon, path: '/prompts' },
  { label: 'Secrets', key: 'secrets', icon: KeyIcon, path: '/secrets' },
  { label: 'Artifacts', key: 'artifacts', icon: ArchiveIcon, path: '/artifacts' },
  { label: 'Telemetry', key: 'telemetry', icon: ActivityIcon, path: '/telemetry' },
  { label: 'Members', key: 'members', icon: UsersIcon },
]

export default function WorkspaceDetail() {
  const qc = useQueryClient()
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const setSelectedWorkspace = useWorkspaceStore((s) => s.setSelectedWorkspace)
  const [showAddMember, setShowAddMember] = useState(false)
  const [newMemberUserId, setNewMemberUserId] = useState('')
  const [newMemberRole, setNewMemberRole] = useState('member')
  const [addError, setAddError] = useState('')
  const [lookingUp, setLookingUp] = useState(false)
  const [addedLabel, setAddedLabel] = useState('')

  const { data: workspace, isLoading } = useQuery({
    queryKey: ['workspace', workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}`).then((r) => r.data),
    enabled: !!workspaceId,
  })

  useEffect(() => {
    if (workspace?.id && workspace?.name) {
      setSelectedWorkspace(workspace.id, workspace.name)
    }
  }, [workspace, setSelectedWorkspace])

  const { data: members } = useQuery({
    queryKey: ['workspace-members', workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data),
    enabled: !!workspaceId,
  })

  const { mutate: addMember, isPending: addPending } = useMutation({
    mutationFn: (payload: { user_id: string; role: string }) =>
      api.post(`/workspaces/${workspaceId}/members`, payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', workspaceId] })
      qc.invalidateQueries({ queryKey: ['workspace', workspaceId] })
      setShowAddMember(false)
      setNewMemberUserId('')
      setNewMemberRole('member')
      setAddError('')
      toast.success('Member added', `${addedLabel} now has access to this workspace.`)
    },
    onError: (err: any) => {
      // Surface backend errors — previously the request failed silently
      // (404 unknown user, 409 already a member, 403 not an admin).
      setAddError(err?.response?.data?.detail || err?.message || 'Could not add the member.')
    },
  })

  const { mutate: removeMember } = useMutation({
    mutationFn: (userId: string) => api.delete(`/workspaces/${workspaceId}/members/${userId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', workspaceId] })
      qc.invalidateQueries({ queryKey: ['workspace', workspaceId] })
      toast.success('Member removed', 'The member no longer has access to this workspace.')
    },
    onError: (err: any) => {
      toast.error('Remove failed', err?.response?.data?.detail || 'Could not remove the member.')
    },
  })

  const { mutate: updateRole } = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) => api.patch(`/workspaces/${workspaceId}/members/${userId}`, { role }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', workspaceId] })
      toast.success('Role updated', 'The member\'s role has been changed.')
    },
    onError: (err: any) => {
      toast.error('Update failed', err?.response?.data?.detail || 'Could not update the role.')
    },
  })

  /**
   * Add a member. The field accepts either a raw user UUID (advanced) or an
   * email address, which is resolved via the API first — no guessing IDs.
   */
  const handleAddMember = async () => {
    const value = newMemberUserId.trim()
    if (!value) return
    setAddError('')
    setLookingUp(true)
    try {
      // Tolerate {braces} around a pasted UUID.
      const normalized = value.replace(/[{}]/g, '')
      const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(normalized)
      let targetId = normalized
      if (!isUuid) {
        const { data: u } = await api.get('/users/lookup', { params: { email: value } })
        targetId = u.id
        setAddedLabel(u.email || u.username || targetId)
      } else {
        setAddedLabel(normalized)
      }
      addMember({ user_id: targetId, role: newMemberRole })
    } catch (err: any) {
      if (err?.response?.status === 404) {
        setAddError('No account found with that email. Ask them to sign in once, then try again.')
      } else {
        setAddError(err?.response?.data?.detail || err?.message || 'Could not resolve that email or user ID.')
      }
    } finally {
      setLookingUp(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-surface-800 rounded" />
        <div className="h-4 w-96 bg-surface-800 rounded" />
        <div className="grid grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-surface-800 rounded-2xl" />
          ))}
        </div>
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-surface-500 text-lg">Workspace not found</p>
        <Link to="/workspaces" className="text-primary-400 hover:text-primary-300 mt-2">
          Back to workspaces
        </Link>
      </div>
    )
  }

  const memberList = Array.isArray(members) ? members : []

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <div>
        <Link
          to="/workspaces"
          className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-surface-200 transition-colors mb-3"
        >
          <ArrowLeftIcon size={14} />
          Back to workspaces
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{workspace.name}</h1>
            {workspace.description && (
              <p className="text-surface-400 text-sm mt-1">{workspace.description}</p>
            )}
          </div>
          <span className="chip">
            {workspace.role ? workspace.role.charAt(0).toUpperCase() + workspace.role.slice(1) : 'Member'}
          </span>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <BotIcon className="w-5 h-5 text-emerald-400 mb-2" />
          <p className="text-lg font-semibold">—</p>
          <p className="text-xs text-surface-500">Agents</p>
        </div>
        <div className="card">
          <WorkflowIcon className="w-5 h-5 text-violet-400 mb-2" />
          <p className="text-lg font-semibold">—</p>
          <p className="text-xs text-surface-500">Workflows</p>
        </div>
        <div className="card">
          <UsersIcon className="w-5 h-5 text-primary-400 mb-2" />
          <p className="text-lg font-semibold">{memberList.length}</p>
          <p className="text-xs text-surface-500">Members</p>
        </div>
        <div className="card">
          <KeyIcon className="w-5 h-5 text-amber-400 mb-2" />
          <p className="text-lg font-semibold">—</p>
          <p className="text-xs text-surface-500">Secrets</p>
        </div>
      </div>

      {/* Domain Tabs */}
      <div>
        <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-3">Workspace Domains</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {tabs.filter((t) => t.key !== 'overview').map((tab) => (
            <Link
              key={tab.key}
              to={`/workspaces/${workspaceId}${tab.path || ''}`}
              className="card flex items-center gap-3 group"
            >
              <tab.icon className="w-4.5 h-4.5 text-surface-400 group-hover:text-primary-400 transition-colors flex-shrink-0" size={18} />
              <span className="text-sm text-surface-300 group-hover:text-white transition-colors">
                {tab.label}
              </span>
            </Link>
          ))}
        </div>
      </div>

      {/* Members Section */}
      <div className="glass-panel p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium flex items-center gap-2"><UsersIcon size={16} />Members ({memberList.length})</h3>
          <button
            onClick={() => { setShowAddMember(true); setAddError('') }}
            className="btn-primary flex items-center gap-1.5 text-xs py-1.5 px-3"
          >
            <PlusIcon size={12} />Add
          </button>
        </div>
        <div className="space-y-2">
          {memberList.length === 0 ? (
            <p className="text-sm text-surface-500 py-4 text-center">No members yet. Add the first member.</p>
          ) : (
            memberList.map((m: any) => (
              <div key={m.user_id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-surface-800/50 hover:bg-surface-800 transition-colors group">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500/20 to-primary-600/20 flex items-center justify-center text-xs font-bold text-primary-400 flex-shrink-0">
                    {(m.username?.[0] || m.email?.[0] || '?').toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <span className="text-sm font-medium truncate block">{m.username || m.email || m.user_id}</span>
                    <span className="text-xs text-surface-500">{m.email}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {/* Role selector */}
                  <select
                    value={m.role}
                    onChange={(e) => {
                      // No-op when the option didn't actually change.
                      if (e.target.value !== m.role) updateRole({ userId: m.user_id, role: e.target.value })
                    }}
                    className={cn(
                      'text-xs rounded-lg px-2 py-1 border transition-colors cursor-pointer',
                      m.role === 'owner' ? 'border-primary-500/30 bg-primary-500/10 text-primary-400' :
                      m.role === 'admin' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' :
                      'border-surface-700 bg-surface-800 text-surface-400'
                    )}
                    disabled={m.role === 'owner'}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                    <option value="owner" disabled>Owner</option>
                  </select>
                  {m.role !== 'owner' && (
                    <button
                      onClick={() => confirm.danger('Remove Member?',`Remove this member from the workspace? This cannot be undone.`,async () => removeMember(m.user_id))}
                      className="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                      title="Remove member"
                    >
                      <UserMinusIcon size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Add Member Modal */}
      {showAddMember && (
        <div data-testid="add-member-modal" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowAddMember(false)}>
          <div className="w-full max-w-sm glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold mb-4">Add Member</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Email or User ID</label>
                <input
                  type="text"
                  placeholder="team@example.com"
                  value={newMemberUserId}
                  onChange={(e) => setNewMemberUserId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddMember() } }}
                  className="input-field"
                />
                <p className="text-xs text-surface-500 mt-1.5">
                  Type their email, or paste the account ID from their Settings → Account ID.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Role</label>
                <select value={newMemberRole} onChange={(e) => setNewMemberRole(e.target.value)} className="input-field">
                  <option value="viewer">Viewer</option>
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              {addError && (
                <div className="px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {addError}
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowAddMember(false)} className="btn-secondary flex-1">Cancel</button>
                <button
                  onClick={handleAddMember}
                  disabled={!newMemberUserId.trim() || lookingUp || addPending}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  {lookingUp || addPending ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <UserCogIcon size={14} />
                  )}
                  {lookingUp || addPending ? 'Adding…' : 'Add'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
