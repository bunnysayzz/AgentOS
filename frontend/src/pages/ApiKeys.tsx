import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'
import { toast } from '@/components/Toast'
import { confirm } from '@/components/ConfirmDialog'
import { SkeletonTable } from '@/components/Skeleton'
import { KeyIcon, PlusIcon, CopyIcon, EyeIcon, EyeOffIcon, Trash2Icon, CheckCircleIcon } from '@/components/Icons'
import { cn } from '@/utils/cn'

interface ApiKey {
  id: string
  name: string
  key_prefix: string
  is_active: boolean
  scopes: string | null
  last_used_at: string | null
  expires_at: string | null
  created_at: string
}

interface ApiKeyCreated extends ApiKey {
  full_key: string
}

export default function ApiKeys() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [showKey, setShowKey] = useState(false)

  const { data: keys, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => api.get<ApiKey[]>('/api-keys/').then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => api.post<ApiKeyCreated>('/api-keys/', { name }),
    onSuccess: (res) => {
      setCreatedKey(res.data)
      toast.success('API key created', 'Copy your key now — it won\'t be shown again.')
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      setKeyName('')
      setShowCreate(false)
    },
    onError: (err: any) => {
      toast.error('Failed to create key', err?.response?.data?.detail)
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}`),
    onSuccess: () => {
      toast.success('API key revoked', 'The key has been deactivated.')
      qc.invalidateQueries({ queryKey: ['api-keys'] })
    },
    onError: (err: any) => {
      toast.error('Failed to revoke key', err?.response?.data?.detail)
    },
  })

  const handleRevoke = (key: ApiKey) => {
    confirm.danger(
      'Revoke API Key?',
      `This will permanently deactivate "${key.name}" (${key.key_prefix}...). Any services using this key will lose access.`,
      async () => { await revokeMutation.mutateAsync(key.id) },
    )
  }

  const handleCopy = (fullKey: string) => {
    navigator.clipboard.writeText(fullKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const keyList: ApiKey[] = Array.isArray(keys) ? keys : []

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-100">API Keys</h1>
          <p className="text-surface-400 mt-1">Manage API keys for programmatic access</p>
        </div>
        <button
          onClick={() => { setShowCreate(true); setCreatedKey(null) }}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon size={16} />
          Create Key
        </button>
      </div>

      {/* Create Form */}
      {showCreate && !createdKey && (
        <div className="glass-panel p-5 space-y-4">
          <h3 className="text-sm font-semibold text-surface-200">New API Key</h3>
          <div className="flex gap-3">
            <input
              type="text"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="e.g., Production CI"
              className="input-field flex-1"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && keyName.trim()) {
                  createMutation.mutate(keyName.trim())
                }
              }}
            />
            <button
              onClick={() => createMutation.mutate(keyName.trim())}
              disabled={!keyName.trim() || createMutation.isPending}
              className="btn-primary"
            >
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </button>
            <button onClick={() => setShowCreate(false)} className="btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Created Key Display */}
      {createdKey && (
        <div className="glass-panel p-5 space-y-4 border-emerald-500/30 bg-emerald-500/5">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircleIcon size={18} />
            <h3 className="text-sm font-semibold">Key Created Successfully</h3>
          </div>
          <div className="bg-surface-950 rounded-xl p-4 border border-surface-700/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-surface-500 font-mono">{createdKey.name}</span>
              <button
                onClick={() => setShowKey(!showKey)}
                className="text-surface-500 hover:text-surface-300 transition-colors"
              >
                {showKey ? <EyeOffIcon size={14} /> : <EyeIcon size={14} />}
              </button>
            </div>
            <div className="flex items-center gap-2">
              <code className={cn(
                'flex-1 text-sm font-mono break-all',
                showKey ? 'text-surface-200' : 'text-surface-500 select-none',
              )}>
                {showKey ? createdKey.full_key : '••••••••••••••••••••••••••••••••'}
              </code>
              <button
                onClick={() => handleCopy(createdKey.full_key)}
                className="flex-shrink-0 p-2 rounded-lg text-surface-500 hover:text-primary-400 hover:bg-primary-500/10 transition-all"
                title="Copy to clipboard"
              >
                {copied ? <CheckCircleIcon size={16} className="text-emerald-400" /> : <CopyIcon size={16} />}
              </button>
            </div>
          </div>
          <p className="text-xs text-amber-400/80 flex items-center gap-1">
            ⚠️ This key will not be shown again. Copy it now.
          </p>
        </div>
      )}

      {/* Keys List */}
      <div className="glass-panel overflow-hidden">
        {isLoading ? (
          <div className="p-5">
            <SkeletonTable rows={3} />
          </div>
        ) : keyList.length === 0 ? (
          <div className="p-8 text-center">
            <div className="w-12 h-12 rounded-2xl bg-surface-800 border border-surface-700/30 flex items-center justify-center mx-auto mb-3">
              <KeyIcon size={22} className="text-surface-500" />
            </div>
            <p className="text-surface-400 text-sm">No API keys yet</p>
            <p className="text-surface-600 text-xs mt-1">Create one to access the API programmatically</p>
          </div>
        ) : (
          <div>
            {keyList.map((key) => (
              <div
                key={key.id}
                className={cn(
                  'flex items-center justify-between px-5 py-4 border-b border-surface-700/30 last:border-0',
                  !key.is_active && 'opacity-50',
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-surface-200">{key.name}</span>
                    {!key.is_active && (
                      <span className="chip text-xs !border-red-500/30 !text-red-400 !bg-red-500/10">
                        Revoked
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <code className="text-xs text-surface-500 font-mono">{key.key_prefix}...</code>
                    <span className="text-surface-700">·</span>
                    <span className="text-xs text-surface-500">
                      Created {new Date(key.created_at).toLocaleDateString()}
                    </span>
                    {key.last_used_at && (
                      <>
                        <span className="text-surface-700">·</span>
                        <span className="text-xs text-surface-500">
                          Used {new Date(key.last_used_at).toLocaleDateString()}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                {key.is_active && (
                  <button
                    onClick={() => handleRevoke(key)}
                    className="flex-shrink-0 p-2 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-all ml-3"
                    title="Revoke key"
                  >
                    <Trash2Icon size={16} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
