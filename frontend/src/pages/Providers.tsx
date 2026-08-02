import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'
import { cn } from '@/utils/cn'
import {
  CheckIcon, CpuIcon, XIcon, KeyIcon, EyeIcon, EyeOffIcon,
  Trash2Icon, RefreshCwIcon, GlobeIcon, BrainIcon,
  ServerIcon, DatabaseIcon, AlertTriangleIcon, PlusIcon,
} from '@/components/Icons'
import { toast } from '@/components/Toast'

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'from-emerald-500 to-emerald-600',
  anthropic: 'from-amber-500 to-amber-600',
  google: 'from-blue-500 to-blue-600',
  groq: 'from-purple-500 to-purple-600',
  cerebras: 'from-orange-500 to-orange-600',
  openrouter: 'from-rose-500 to-rose-600',
  mistral: 'from-sky-500 to-sky-600',
  huggingface: 'from-yellow-500 to-yellow-600',
  nvidia_nim: 'from-green-500 to-green-600',
  github_models: 'from-gray-500 to-gray-600',
  sambanova: 'from-teal-500 to-teal-600',
  deepseek: 'from-blue-700 to-indigo-700',
  custom: 'from-surface-500 to-surface-600',
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google Gemini',
  groq: 'Groq', mistral: 'Mistral AI', deepseek: 'DeepSeek',
  github_models: 'GitHub Models', nvidia_nim: 'NVIDIA NIM',
  sambanova: 'SambaNova', llmapi: 'LLM API',
  openrouter: 'OpenRouter', cerebras: 'Cerebras',
  huggingface: 'HuggingFace', together_ai: 'Together AI',
  ollama: 'Ollama', azure: 'Azure OpenAI',
  custom: 'Custom',
}

function ProviderIcon({ icon, size = 18 }: { icon: string; size?: number }) {
  const iconMap: Record<string, React.ReactNode> = {
    openai: <CpuIcon size={size} className="text-white" />,
    anthropic: <BrainIcon size={size} className="text-white" />,
    google: <GlobeIcon size={size} className="text-white" />,
    groq: <ZapIcon size={size} className="text-white" />,
    mistral: <BrainIcon size={size} className="text-white" />,
    deepseek: <BrainIcon size={size} className="text-white" />,
    nvidia: <CpuIcon size={size} className="text-white" />,
    github: <ServerIcon size={size} className="text-white" />,
    sambanova: <CpuIcon size={size} className="text-white" />,
    azure: <DatabaseIcon size={size} className="text-white" />,
    ollama: <CpuIcon size={size} className="text-white" />,
    custom: <KeyIcon size={size} className="text-white" />,
  }
  return <>{iconMap[icon] || <CpuIcon size={size} className="text-white" />}</>
}

function getLabel(provider: string): string {
  return PROVIDER_LABELS[provider] || provider.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

function getColor(provider: string): string {
  return PROVIDER_COLORS[provider] || 'from-surface-500 to-surface-600'
}

interface ProviderConfig {
  provider: string
  default_model: string | null
  is_configured: boolean
  base_url: string | null
  created_at: string
}

interface DetectResult {
  detected: boolean
  provider: string | null
  label: string
  base_url: string | null
  default_model: string | null
}

interface TestResult {
  provider: string
  success: boolean
  message: string
}

type AddStatus = 'idle' | 'detecting' | 'saving' | 'done' | 'error'

export default function Providers() {
  const qc = useQueryClient()
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [addStatus, setAddStatus] = useState<AddStatus>('idle')
  const [addResult, setAddResult] = useState<{ label: string; provider: string; color: string } | null>(null)
  const [addError, setAddError] = useState('')
  const [editProvider, setEditProvider] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({})
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({})

  const { data: configs, isLoading } = useQuery({
    queryKey: ['provider-configs'],
    queryFn: () => api.get('/mcp/providers').then((r) => r.data),
  })

  const configList: ProviderConfig[] = Array.isArray(configs) ? configs : []

  // ── Add / Detect + Save in one click ──
  const handleAdd = async () => {
    const key = apiKeyInput.trim()
    if (!key || key.length < 3) {
      toast.error('Invalid key', 'Please paste a valid API key')
      return
    }

    setAddStatus('detecting')
    setAddResult(null)
    setAddError('')

    try {
      // Step 1: Detect provider
      const detectRes = await api.get('/mcp/providers/detect', { params: { api_key: key } })
      const detected: DetectResult = detectRes.data

      if (!detected.detected) {
        setAddStatus('error')
        setAddError('Could not identify this key. Try a different key format.')
        return
      }

      // Step 2: Save provider
      setAddStatus('saving')
      await api.put(`/mcp/providers/${detected.provider}`, {
        provider: detected.provider,
        api_key: key,
        base_url: detected.base_url || null,
        default_model: detected.default_model || null,
      })

      // Success!
      qc.invalidateQueries({ queryKey: ['provider-configs'] })
      setAddStatus('done')
      setAddResult({
        label: detected.label,
        provider: detected.provider!,
        color: getColor(detected.provider!),
      })
      toast.success(`${detected.label} configured!`)

      // Auto-test in background
      setTimeout(() => testMutation.mutate(detected.provider!), 500)

      // Reset after 3s
      setTimeout(() => {
        setAddStatus('idle')
        setAddResult(null)
        setApiKeyInput('')
      }, 3000)

    } catch (err: any) {
      setAddStatus('error')
      setAddError(err?.response?.data?.detail || err?.message || 'Connection error')
    }
  }

  // ── Mutations ──
  const deleteMutation = useMutation({
    mutationFn: (provider: string) => api.delete(`/mcp/providers/${provider}`),
    onSuccess: (_, provider) => {
      qc.invalidateQueries({ queryKey: ['provider-configs'] })
      toast.success(`Removed ${getLabel(provider)}`)
      setEditProvider(null)
    },
    onError: (err: any, _provider: string) => {
      toast.error('Failed to remove', err?.response?.data?.detail || err.message)
    },
  })

  const testMutation = useMutation({
    mutationFn: (provider: string) =>
      api.post(`/mcp/providers/${provider}/test`).then((r) => r.data),
    onSuccess: (data: TestResult) => {
      setTestResults((prev) => ({ ...prev, [data.provider]: data }))
      if (data.success) toast.success(`${getLabel(data.provider)}: Connected!`)
      else toast.error(`${getLabel(data.provider)}: ${data.message}`)
    },
    onError: (err: any, provider: string) => {
      const msg = err?.response?.data?.detail || err?.message || 'Connection failed'
      setTestResults((prev) => ({ ...prev, [provider]: { provider, success: false, message: msg } }))
    },
  })

  const saveMutation = useMutation({
    mutationFn: ({ provider, data }: { provider: string; data: any }) =>
      api.put(`/mcp/providers/${provider}`, data).then((r) => r.data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['provider-configs'] })
      toast.success(`${getLabel(vars.provider)} updated!`)
      setEditProvider(null)
    },
    onError: (err: any, _vars) => {
      toast.error(`Failed to update`, err?.response?.data?.detail || err.message)
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">LLM Providers</h1>
          <p className="text-surface-400 text-sm mt-1">
            Add API keys for AI providers. We auto-detect the provider & model.
          </p>
        </div>
      </div>

      {/* ── Add Provider Form ── */}
      <div className={cn(
        'glass-panel p-5 transition-all duration-300',
        addStatus === 'done' && 'border-emerald-500/30'
      )}>
        <div className="flex items-center gap-3 mb-3">
          <div className={cn(
            'w-10 h-10 rounded-xl flex items-center justify-center shadow-lg transition-all duration-500',
            addStatus === 'done'
              ? 'bg-gradient-to-br from-emerald-500 to-emerald-700'
              : 'bg-gradient-to-br from-primary-500 to-primary-700'
          )}>
            {addStatus === 'done' ? <CheckIcon size={18} className="text-white" /> : <KeyIcon size={18} className="text-white" />}
          </div>
          <div>
            <h2 className="font-semibold text-sm">Add Provider</h2>
            <p className="text-xs text-surface-500">Paste your API key and click the button</p>
          </div>
        </div>

        <div className="flex gap-3">
          <input
            type="text"
            value={apiKeyInput}
            onChange={(e) => { setApiKeyInput(e.target.value); if (addStatus !== 'idle') { setAddStatus('idle'); setAddResult(null); setAddError('') }}}
            placeholder="Paste your API key here..."
            className={cn(
              'input-field flex-1 font-mono text-sm transition-all',
              addStatus === 'done' && 'border-emerald-500/50 bg-emerald-500/5',
              addStatus === 'error' && 'border-red-500/50',
            )}
            autoComplete="off"
            spellCheck={false}
            disabled={addStatus === 'detecting' || addStatus === 'saving'}
          />
          <button
            onClick={handleAdd}
            disabled={!apiKeyInput.trim() || addStatus === 'detecting' || addStatus === 'saving'}
            className="btn-primary flex items-center gap-2 whitespace-nowrap min-w-[120px] justify-center"
          >
            {addStatus === 'detecting' || addStatus === 'saving' ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {addStatus === 'detecting' ? 'Detecting...' : 'Saving...'}
              </>
            ) : (
              <>
                <PlusIcon size={16} />
                Add Provider
              </>
            )}
          </button>
        </div>

        {/* Status messages */}
        {addStatus === 'done' && addResult && (
          <div className="mt-3 flex items-center gap-3 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 animate-slide-in-right">
            <div className={cn('w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center shadow-sm', addResult.color)}>
              <ProviderIcon icon={addResult.provider} size={14} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-emerald-400">{addResult.label}</p>
              <p className="text-xs text-emerald-500/70">Configured! Testing connection...</p>
            </div>
          </div>
        )}

        {addStatus === 'error' && (
          <div className="mt-3 flex items-center gap-2 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            <AlertTriangleIcon size={16} />
            <span>{addError}</span>
          </div>
        )}
      </div>

      {/* ── Configured Providers ── */}
      {isLoading ? (
        <div className="grid gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-panel p-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-surface-800" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-32 bg-surface-800 rounded" />
                  <div className="h-3 w-48 bg-surface-800 rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : configList.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-surface-800 border border-surface-700/30 flex items-center justify-center mx-auto mb-4">
            <KeyIcon size={28} className="text-surface-500" />
          </div>
          <h3 className="text-lg font-medium text-surface-300 mb-1">No providers configured</h3>
          <p className="text-sm text-surface-500 max-w-md mx-auto">
            Paste an API key above and click "Add Provider". We support 30+ providers.
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {configList.map((config) => {
            const providerId = config.provider
            const label = getLabel(providerId)
            const color = getColor(providerId)
            const testResult = testResults[providerId]
            const model = config.default_model || 'auto'

            return (
              <div key={providerId} className="glass-panel overflow-hidden transition-all duration-200 hover:border-surface-600/50">
                <div className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className={cn('w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center flex-shrink-0 shadow-md', color)}>
                        <ProviderIcon icon={providerId} size={16} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-sm">{label}</h3>
                          {config.is_configured && (
                            <span className="text-[10px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-2 py-0.5 flex items-center gap-1">
                              <CheckIcon size={8} />Active
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-surface-500 mt-0.5">
                          Model: <span className="font-mono text-surface-400">{model}</span>
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <button
                          onClick={() => testMutation.mutate(providerId)}
                          disabled={testMutation.isPending}
                          className="btn-secondary text-xs py-1.5 px-2.5 flex items-center gap-1"
                          title="Test connection"
                        >
                          <RefreshCwIcon size={12} />
                        </button>
                        <button
                          onClick={() => { if (window.confirm(`Remove ${label} API key?`)) deleteMutation.mutate(providerId) }}
                          className="btn-secondary text-xs py-1.5 px-2.5 text-red-400 hover:text-red-300 flex items-center gap-1"
                        >
                          <Trash2Icon size={12} />
                        </button>
                        <button
                          onClick={() => setEditProvider(editProvider === providerId ? null : providerId)}
                          className={cn('btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5', editProvider === providerId && 'bg-red-500 hover:bg-red-600')}
                        >
                          {editProvider === providerId ? <XIcon size={12} /> : <KeyIcon size={12} />}
                          {editProvider === providerId ? 'Close' : 'Update'}
                        </button>
                      </div>
                    </div>
                  </div>

                  {testResult && (
                    <div className={cn('mt-2 px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5', testResult.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400')}>
                      {testResult.success ? <CheckIcon size={12} /> : <XIcon size={12} />}
                      {testResult.message}
                    </div>
                  )}

                  {editProvider === providerId && (
                    <div className="mt-3 pt-3 border-t border-surface-700/30">
                      <UpdateKeyForm
                        showPassword={!!showPassword[providerId]}
                        onTogglePassword={() => setShowPassword((p) => ({ ...p, [providerId]: !p[providerId] }))}
                        onSave={(apiKey) => {
                          saveMutation.mutate({
                            provider: providerId,
                            data: { provider: providerId, api_key: apiKey, base_url: config.base_url, default_model: config.default_model },
                          })
                        }}
                        isPending={saveMutation.isPending}
                      />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function UpdateKeyForm({ showPassword, onTogglePassword, onSave, isPending }: {
  showPassword: boolean
  onTogglePassword: () => void
  onSave: (key: string) => void
  isPending: boolean
}) {
  const [key, setKey] = useState('')
  return (
    <div className="flex gap-2">
      <div className="relative flex-1">
        <input type={showPassword ? 'text' : 'password'} placeholder="Enter new API key..." value={key}
          onChange={(e) => setKey(e.target.value)} className="input-field w-full font-mono text-sm pr-10" />
        <button type="button" onClick={onTogglePassword} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300">
          {showPassword ? <EyeOffIcon size={14} /> : <EyeIcon size={14} />}
        </button>
      </div>
      <button onClick={() => onSave(key)} disabled={isPending || !key.trim()} className="btn-primary flex items-center gap-1.5 text-sm">
        {isPending ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <CheckIcon size={14} />}
        Save
      </button>
    </div>
  )
}

function ZapIcon({ className, size = 18 }: { className?: string; size?: number }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  )
}
