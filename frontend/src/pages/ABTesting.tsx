import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  TrendingUpIcon, PlusIcon, PlayIcon, StopIcon, RefreshCwIcon, EyeIcon,
  TrophyIcon, CheckIcon, XIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import WorkspaceRequired from '@/components/WorkspaceRequired'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface ABVariant {
  id: string
  test_id: string
  name: string
  content?: string | null
  is_control: boolean
  created_at: string
}

interface ABTest {
  id: string
  name: string
  description?: string | null
  prompt_id?: string | null
  status: 'draft' | 'running' | 'completed'
  traffic_split: number
  created_at: string
  updated_at: string
  started_at?: string | null
  completed_at?: string | null
}

interface VariantStats {
  variant: ABVariant
  total_runs: number
  avg_score?: number | null
  min_score?: number | null
  max_score?: number | null
  avg_latency_ms?: number | null
  avg_tokens?: number | null
  positive_feedback: number
  negative_feedback: number
}

interface ABResults {
  test_id: string
  variants: Record<string, VariantStats>
  winner?: string | null
}

interface Prompt {
  id: string
  name: string
}

const statusColor: Record<string, string> = {
  draft: 'bg-surface-700/40 text-surface-400',
  running: 'bg-emerald-500/10 text-emerald-400',
  completed: 'bg-blue-500/10 text-blue-400',
}

function fmtDate(iso?: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function ABTesting() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId

  const [showCreate, setShowCreate] = useState(false)
  const [testName, setTestName] = useState('')
  const [testDesc, setTestDesc] = useState('')
  const [testPromptId, setTestPromptId] = useState('')
  const [variants, setVariants] = useState([{ name: 'Control', content: '' }, { name: 'Variant B', content: '' }])
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null)

  const { data: tests } = useQuery({
    queryKey: ['ab-tests', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/ab-tests`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: prompts } = useQuery({
    queryKey: ['prompts', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/prompts`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: resultsData } = useQuery({
    queryKey: ['ab-results', wsId, selectedTestId],
    queryFn: () => api.get(`/workspaces/${wsId}/ab-tests/${selectedTestId}/results`).then((r) => r.data),
    enabled: !!wsId && !!selectedTestId,
  })

  const testList: ABTest[] = Array.isArray(tests) ? tests : []
  const promptList: Prompt[] = Array.isArray(prompts) ? prompts : []
  const selectedTest = testList.find((t) => t.id === selectedTestId) || null
  const results: ABResults | null = resultsData || null

  const { mutate: createTest, isPending: creating } = useMutation({
    mutationFn: (d: { name: string; description?: string; prompt_id?: string; variants: { name: string; content: string }[] }) =>
      api.post(`/workspaces/${wsId}/ab-tests`, d).then((r) => r.data),
    onSuccess: (test: ABTest) => {
      qc.invalidateQueries({ queryKey: ['ab-tests', wsId] })
      setTestName('')
      setTestDesc('')
      setTestPromptId('')
      setVariants([{ name: 'Control', content: '' }, { name: 'Variant B', content: '' }])
      setShowCreate(false)
      setSelectedTestId(test.id)
      toast.success('A/B test created', test.name)
    },
    onError: (err: any) => toast.error('Failed to create test', err?.response?.data?.detail),
  })

  const { mutate: startTest, isPending: starting } = useMutation({
    mutationFn: (id: string) => api.post(`/workspaces/${wsId}/ab-tests/${id}/start`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ab-tests', wsId] })
      toast.success('Test started')
    },
    onError: (err: any) => toast.error('Failed to start test', err?.response?.data?.detail),
  })

  const { mutate: stopTest, isPending: stopping } = useMutation({
    mutationFn: (id: string) => api.post(`/workspaces/${wsId}/ab-tests/${id}/stop`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ab-tests', wsId] })
      toast.success('Test stopped')
    },
    onError: (err: any) => toast.error('Failed to stop test', err?.response?.data?.detail),
  })

  if (!wsId) return <WorkspaceRequired title="A/B Testing" description="Select a workspace to run prompt experiments" />

  const variantStats: VariantStats[] = results
    ? Object.values(results.variants).filter((v) => v.variant)
    : []
  const winner = results?.winner ? results.variants[results.winner] : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">A/B Testing</h1>
          <p className="text-surface-400 text-sm mt-1">Split-test prompt variants and compare performance</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          <button
            onClick={() => setShowCreate(!showCreate)}
            className={cn('flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all', showCreate ? 'bg-surface-800 text-surface-300 border border-surface-700/50' : 'btn-primary')}
          >
            {showCreate ? <XIcon size={16} /> : <PlusIcon size={16} />}
            {showCreate ? 'Cancel' : 'New Test'}
          </button>
        </div>
      </div>

      {/* Create test */}
      {showCreate && (
        <div className="glass-panel p-5 space-y-4">
          <h3 className="font-medium flex items-center gap-2">
            <PlusIcon size={16} className="text-primary-400" />
            Create A/B Test
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label>
              <input
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                placeholder="e.g. Onboarding prompt v2"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Description</label>
              <input
                value={testDesc}
                onChange={(e) => setTestDesc(e.target.value)}
                placeholder="What are you testing?"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Prompt (optional)</label>
              <select value={testPromptId} onChange={(e) => setTestPromptId(e.target.value)} className="input-field">
                <option value="">No linked prompt</option>
                {promptList.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5">Variants</label>
            <div className="space-y-2">
              {variants.map((v, i) => (
                <div key={i} className="grid grid-cols-1 md:grid-cols-[140px_1fr_auto] gap-2 items-center">
                  <input
                    value={v.name}
                    onChange={(e) => {
                      const next = [...variants]
                      next[i].name = e.target.value
                      setVariants(next)
                    }}
                    placeholder={i === 0 ? 'Control' : `Variant ${String.fromCharCode(65 + i)}`}
                    className="input-field text-sm"
                  />
                  <textarea
                    value={v.content}
                    onChange={(e) => {
                      const next = [...variants]
                      next[i].content = e.target.value
                      setVariants(next)
                    }}
                    placeholder="Prompt content…"
                    className="input-field font-mono text-sm min-h-[48px] resize-y"
                    rows={1}
                  />
                  <button
                    onClick={() => {
                      if (variants.length <= 2) return
                      setVariants(variants.filter((_, j) => j !== i))
                    }}
                    disabled={variants.length <= 2}
                    className="p-2 rounded-lg text-surface-500 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-30 transition-all"
                    title="Remove variant"
                  >
                    <XIcon size={14} />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={() => setVariants([...variants, { name: `Variant ${String.fromCharCode(65 + variants.length)}`, content: '' }])}
              className="mt-2 text-xs text-surface-400 hover:text-primary-400 flex items-center gap-1 transition-all"
            >
              <PlusIcon size={12} />
              Add variant
            </button>
          </div>

          <button
            onClick={() => createTest({
              name: testName,
              description: testDesc || undefined,
              prompt_id: testPromptId || undefined,
              variants: variants.map((v) => ({ name: v.name, content: v.content })),
            })}
            disabled={!testName.trim() || creating || variants.some((v) => !v.name.trim())}
            className="btn-primary flex items-center gap-2"
          >
            {creating ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <PlusIcon size={16} />}
            Create Test
          </button>
        </div>
      )}

      {/* Tests + Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tests list */}
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2">
              <TrendingUpIcon size={16} className="text-primary-400" />
              Tests ({testList.length})
            </h3>
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ['ab-tests', wsId] })}
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all"
            >
              <RefreshCwIcon size={14} />
            </button>
          </div>

          {testList.length === 0 ? (
            <div className="py-8 text-center">
              <TrendingUpIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">No A/B tests yet</p>
              <p className="text-xs text-surface-600 mt-1">Create a test to compare prompt variants</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[420px] overflow-y-auto">
              {testList.map((test) => (
                <div
                  key={test.id}
                  onClick={() => setSelectedTestId(test.id)}
                  className={cn(
                    'p-3 rounded-xl cursor-pointer transition-all border',
                    selectedTestId === test.id
                      ? 'bg-primary-500/10 border-primary-500/30'
                      : 'bg-surface-800/50 border-transparent hover:bg-surface-800',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-surface-200">{test.name}</p>
                    <span className={cn('chip text-[10px]', statusColor[test.status] || 'bg-surface-800 text-surface-400')}>{test.status}</span>
                  </div>
                  {test.description && <p className="text-xs text-surface-500 mt-1 line-clamp-2">{test.description}</p>}
                  <div className="flex items-center justify-between mt-1.5">
                    <p className="text-[11px] text-surface-600">Traffic split: {test.traffic_split}% / {100 - test.traffic_split}%</p>
                    <div className="flex items-center gap-1">
                      {test.status === 'draft' && (
                        <button
                          onClick={(e) => { e.stopPropagation(); startTest(test.id) }}
                          disabled={starting}
                          className="p-1 rounded text-surface-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-all"
                          title="Start"
                        >
                          <PlayIcon size={12} />
                        </button>
                      )}
                      {test.status === 'running' && (
                        <button
                          onClick={(e) => { e.stopPropagation(); stopTest(test.id) }}
                          disabled={stopping}
                          className="p-1 rounded text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                          title="Stop"
                        >
                          <StopIcon size={12} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail */}
        <div className="glass-panel p-5">
          {!selectedTest ? (
            <div className="py-12 text-center">
              <EyeIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">Select a test to see variant results</p>
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <h3 className="font-medium">{selectedTest.name}</h3>
                {selectedTest.description && <p className="text-xs text-surface-500 mt-0.5">{selectedTest.description}</p>}
                <p className="text-[11px] text-surface-600 mt-1">
                  Created {fmtDate(selectedTest.created_at)}
                  {selectedTest.started_at && ` · started ${fmtDate(selectedTest.started_at)}`}
                  {selectedTest.completed_at && ` · completed ${fmtDate(selectedTest.completed_at)}`}
                </p>
              </div>

              {winner && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-300">
                  <TrophyIcon size={16} className="flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium">Winner: {winner.variant.name}</p>
                    <p className="text-xs mt-0.5 opacity-80">
                      Avg score {winner.avg_score ?? '—'} across {winner.total_runs} runs
                    </p>
                  </div>
                </div>
              )}

              {variantStats.length === 0 ? (
                <p className="text-xs text-surface-600 py-8 text-center">No variants with results yet — start the test and record results to see comparisons</p>
              ) : (
                <div className="space-y-3">
                  {variantStats.map((stats) => (
                    <div key={stats.variant.id} className="p-4 rounded-xl bg-surface-800/50 border border-surface-700/30">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-surface-200">{stats.variant.name}</p>
                          {stats.variant.is_control && <span className="chip text-[10px]">control</span>}
                          {results?.winner === stats.variant.id && (
                            <span className="chip text-[10px] bg-amber-500/10 text-amber-400">winner</span>
                          )}
                        </div>
                        <span className="text-xs text-surface-500">{stats.total_runs} runs</span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                        <div className="p-2 rounded-lg bg-surface-900/50">
                          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Avg score</p>
                          <p className="text-sm font-bold text-surface-100 mt-0.5">{stats.avg_score ?? '—'}</p>
                        </div>
                        <div className="p-2 rounded-lg bg-surface-900/50">
                          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Range</p>
                          <p className="text-sm font-bold text-surface-100 mt-0.5">
                            {stats.min_score != null && stats.max_score != null ? `${stats.min_score}–${stats.max_score}` : '—'}
                          </p>
                        </div>
                        <div className="p-2 rounded-lg bg-surface-900/50">
                          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Latency</p>
                          <p className="text-sm font-bold text-surface-100 mt-0.5">{stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : '—'}</p>
                        </div>
                        <div className="p-2 rounded-lg bg-surface-900/50">
                          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Tokens</p>
                          <p className="text-sm font-bold text-surface-100 mt-0.5">{stats.avg_tokens ?? '—'}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 mt-3 text-[11px] text-surface-500">
                        <span className="flex items-center gap-1">
                          <CheckIcon size={11} className="text-emerald-400" />
                          {stats.positive_feedback} positive
                        </span>
                        <span className="flex items-center gap-1">
                          <XIcon size={11} className="text-red-400" />
                          {stats.negative_feedback} negative
                        </span>
                      </div>

                      {stats.variant.content && (
                        <p className="text-[11px] text-surface-500 mt-2 font-mono line-clamp-3 border-t border-surface-700/30 pt-2">{stats.variant.content}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
