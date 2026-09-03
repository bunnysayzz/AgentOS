import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ListOrderedIcon, PlusIcon, PlayIcon, RefreshCwIcon, CheckCircleIcon,
  XCircleIcon, AlertTriangleIcon, EyeIcon, CheckIcon, XIcon, RocketIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import WorkspaceRequired from '@/components/WorkspaceRequired'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface TestCase {
  id: string
  input: string
  expected_output?: string | null
  criteria?: string | null
  tags?: string[]
  created_at: string
}

interface EvalSuite {
  id: string
  name: string
  description?: string | null
  test_cases: TestCase[]
  created_at: string
  updated_at: string
}

interface EvalResult {
  id: string
  test_case_id: string
  input: string
  actual_output: string
  score: number
  judge_reasoning?: string | null
  passed: boolean
  created_at: string
}

interface EvalRun {
  id: string
  suite_id: string
  agent_id?: string | null
  model_name?: string | null
  status: string
  results: EvalResult[]
  summary?: {
    total: number
    passed: number
    failed: number
    pass_rate: number
    avg_score: number
    min_score: number
    max_score: number
  } | null
  created_at: string
  completed_at?: string | null
}

interface Regression {
  regression_detected: boolean
  current_pass_rate?: number
  previous_pass_rate?: number
  threshold?: number
  message: string
}

interface Agent {
  id: string
  name: string
}

const statusColor: Record<string, string> = {
  pending: 'bg-amber-500/10 text-amber-400',
  running: 'bg-blue-500/10 text-blue-400',
  completed: 'bg-emerald-500/10 text-emerald-400',
  failed: 'bg-red-500/10 text-red-400',
}

function fmtDate(iso?: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function Evaluations() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId

  const [showCreateSuite, setShowCreateSuite] = useState(false)
  const [suiteName, setSuiteName] = useState('')
  const [suiteDesc, setSuiteDesc] = useState('')
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  // New test case form
  const [tcInput, setTcInput] = useState('')
  const [tcExpected, setTcExpected] = useState('')
  const [tcCriteria, setTcCriteria] = useState('')

  // New run form
  const [runAgentId, setRunAgentId] = useState('')
  const [runModel, setRunModel] = useState('')

  // Record result form
  const [showRecordResult, setShowRecordResult] = useState(false)
  const [resInput, setResInput] = useState('')
  const [resOutput, setResOutput] = useState('')
  const [resScore, setResScore] = useState('0.9')
  const [resReasoning, setResReasoning] = useState('')

  const [regression, setRegression] = useState<Regression | null>(null)

  const { data: suites } = useQuery({
    queryKey: ['eval-suites', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/evaluations/suites`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: agents } = useQuery({
    queryKey: ['agents', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/agents/`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: runs } = useQuery({
    queryKey: ['eval-runs', wsId, selectedSuiteId],
    queryFn: () => api.get(`/workspaces/${wsId}/evaluations/runs`, { params: { suite_id: selectedSuiteId ?? undefined } }).then((r) => r.data),
    enabled: !!wsId && !!selectedSuiteId,
  })

  const suiteList: EvalSuite[] = Array.isArray(suites) ? suites : []
  const runList: EvalRun[] = Array.isArray(runs) ? runs : []
  const agentList: Agent[] = Array.isArray(agents) ? agents : []
  const selectedSuite = suiteList.find((s) => s.id === selectedSuiteId) || null
  const selectedRun = runList.find((r) => r.id === selectedRunId) || null

  const { mutate: createSuite, isPending: creatingSuite } = useMutation({
    mutationFn: (d: { name: string; description?: string }) =>
      api.post(`/workspaces/${wsId}/evaluations/suites`, d).then((r) => r.data),
    onSuccess: (suite: EvalSuite) => {
      qc.invalidateQueries({ queryKey: ['eval-suites', wsId] })
      setSuiteName('')
      setSuiteDesc('')
      setShowCreateSuite(false)
      setSelectedSuiteId(suite.id)
      setSelectedRunId(null)
      toast.success('Suite created', suite.name)
    },
    onError: (err: any) => toast.error('Failed to create suite', err?.response?.data?.detail),
  })

  const { mutate: addTestCase, isPending: addingTc } = useMutation({
    mutationFn: (d: { input: string; expected_output?: string; criteria?: string }) =>
      api.post(`/workspaces/${wsId}/evaluations/suites/${selectedSuiteId}/test-cases`, d).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eval-suites', wsId] })
      setTcInput('')
      setTcExpected('')
      setTcCriteria('')
      toast.success('Test case added')
    },
    onError: (err: any) => toast.error('Failed to add test case', err?.response?.data?.detail),
  })

  const { mutate: createRun, isPending: creatingRun } = useMutation({
    mutationFn: (d: { suite_id: string; agent_id?: string; model_name?: string }) =>
      api.post(`/workspaces/${wsId}/evaluations/runs`, d).then((r) => r.data),
    onSuccess: (run: EvalRun) => {
      qc.invalidateQueries({ queryKey: ['eval-runs', wsId, selectedSuiteId] })
      setRunAgentId('')
      setRunModel('')
      setSelectedRunId(run.id)
      setRegression(null)
      toast.success('Run created', run.id.slice(0, 8))
    },
    onError: (err: any) => toast.error('Failed to create run', err?.response?.data?.detail),
  })

  const { mutate: recordResult, isPending: recording } = useMutation({
    mutationFn: (d: { test_case_id: string; input: string; actual_output: string; score: number; judge_reasoning?: string }) =>
      api.post(`/workspaces/${wsId}/evaluations/runs/${selectedRunId}/results`, d).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eval-runs', wsId, selectedSuiteId] })
      setResInput('')
      setResOutput('')
      setResReasoning('')
      setShowRecordResult(false)
      toast.success('Result recorded')
    },
    onError: (err: any) => toast.error('Failed to record result', err?.response?.data?.detail),
  })

  const { mutate: completeRun, isPending: completing } = useMutation({
    mutationFn: () => api.post(`/workspaces/${wsId}/evaluations/runs/${selectedRunId}/complete`).then((r) => r.data),
    onSuccess: (run: EvalRun) => {
      qc.invalidateQueries({ queryKey: ['eval-runs', wsId, selectedSuiteId] })
      setSelectedRunId(run.id)
      setRegression(null)
      toast.success('Run completed')
    },
    onError: (err: any) => toast.error('Failed to complete run', err?.response?.data?.detail),
  })

  const { mutate: executeRun, isPending: executingRun } = useMutation({
    mutationFn: () => api.post(`/workspaces/${wsId}/evaluations/runs/${selectedRunId}/execute`).then((r) => r.data),
    onSuccess: (run: EvalRun) => {
      qc.invalidateQueries({ queryKey: ['eval-runs', wsId, selectedSuiteId] })
      setSelectedRunId(run.id)
      setRegression(null)
      toast.success('Run executed', `Pass rate ${run.summary?.pass_rate ?? 0}%`)
    },
    onError: (err: any) => toast.error('Auto-run failed', err?.response?.data?.detail),
  })

  const { mutate: checkRegression, isPending: checkingRegression } = useMutation({
    mutationFn: () => api.get(`/workspaces/${wsId}/evaluations/runs/${selectedRunId}/regression`).then((r) => r.data),
    onSuccess: (data: Regression) => {
      setRegression(data)
      if (data.regression_detected) {
        toast.warning('Regression detected', data.message)
      } else {
        toast.success('No regression', data.message)
      }
    },
    onError: (err: any) => toast.error('Regression check failed', err?.response?.data?.detail),
  })

  if (!wsId) return <WorkspaceRequired title="Evaluations" description="Select a workspace to manage evaluation suites" />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Evaluations</h1>
          <p className="text-surface-400 text-sm mt-1">Suites, test cases, runs, and regression checks</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          <button
            onClick={() => setShowCreateSuite(!showCreateSuite)}
            className={cn('flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all', showCreateSuite ? 'bg-surface-800 text-surface-300 border border-surface-700/50' : 'btn-primary')}
          >
            {showCreateSuite ? <XIcon size={16} /> : <PlusIcon size={16} />}
            {showCreateSuite ? 'Cancel' : 'New Suite'}
          </button>
        </div>
      </div>

      {/* Create suite */}
      {showCreateSuite && (
        <div className="glass-panel p-5 space-y-4">
          <h3 className="font-medium flex items-center gap-2">
            <PlusIcon size={16} className="text-primary-400" />
            Create Evaluation Suite
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label>
              <input
                value={suiteName}
                onChange={(e) => setSuiteName(e.target.value)}
                placeholder="e.g. Customer support quality"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Description</label>
              <input
                value={suiteDesc}
                onChange={(e) => setSuiteDesc(e.target.value)}
                placeholder="What does this suite measure?"
                className="input-field"
              />
            </div>
          </div>
          <button
            onClick={() => createSuite({ name: suiteName, description: suiteDesc || undefined })}
            disabled={!suiteName.trim() || creatingSuite}
            className="btn-primary flex items-center gap-2"
          >
            {creatingSuite ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <PlusIcon size={16} />}
            Create Suite
          </button>
        </div>
      )}

      {/* Suites + Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Suites list */}
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2">
              <ListOrderedIcon size={16} className="text-primary-400" />
              Suites ({suiteList.length})
            </h3>
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ['eval-suites', wsId] })}
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all"
            >
              <RefreshCwIcon size={14} />
            </button>
          </div>

          {suiteList.length === 0 ? (
            <div className="py-8 text-center">
              <ListOrderedIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">No evaluation suites yet</p>
              <p className="text-xs text-surface-600 mt-1">Create a suite to start scoring agent outputs</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[420px] overflow-y-auto">
              {suiteList.map((suite) => (
                <div
                  key={suite.id}
                  onClick={() => { setSelectedSuiteId(suite.id); setSelectedRunId(null); setRegression(null) }}
                  className={cn(
                    'p-3 rounded-xl cursor-pointer transition-all border',
                    selectedSuiteId === suite.id
                      ? 'bg-primary-500/10 border-primary-500/30'
                      : 'bg-surface-800/50 border-transparent hover:bg-surface-800',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-surface-200">{suite.name}</p>
                    <span className="chip text-[10px]">{suite.test_cases?.length || 0} cases</span>
                  </div>
                  {suite.description && (
                    <p className="text-xs text-surface-500 mt-1 line-clamp-2">{suite.description}</p>
                  )}
                  <p className="text-[11px] text-surface-600 mt-1.5">{fmtDate(suite.created_at)}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Suite detail */}
        <div className="glass-panel p-5">
          {!selectedSuite ? (
            <div className="py-12 text-center">
              <EyeIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">Select a suite to manage test cases and runs</p>
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <h3 className="font-medium">{selectedSuite.name}</h3>
                {selectedSuite.description && <p className="text-xs text-surface-500 mt-0.5">{selectedSuite.description}</p>}
              </div>

              {/* Test cases */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">Test cases ({selectedSuite.test_cases?.length || 0})</p>
                </div>
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {(selectedSuite.test_cases || []).map((tc) => (
                    <div key={tc.id} className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                      <p className="text-sm text-surface-200">{tc.input}</p>
                      {tc.expected_output && <p className="text-xs text-surface-500 mt-1"><span className="text-surface-400">Expected:</span> {tc.expected_output}</p>}
                      {(tc.tags || []).length > 0 && (
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          {tc.tags!.map((t) => (
                            <span key={t} className="chip text-[10px]">{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Add test case */}
                <div className="mt-3 space-y-2">
                  <textarea
                    value={tcInput}
                    onChange={(e) => setTcInput(e.target.value)}
                    placeholder="Test case input…"
                    className="input-field font-mono text-sm min-h-[60px] resize-y"
                    rows={2}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input
                      value={tcExpected}
                      onChange={(e) => setTcExpected(e.target.value)}
                      placeholder="Expected output (optional)"
                      className="input-field text-sm"
                    />
                    <input
                      value={tcCriteria}
                      onChange={(e) => setTcCriteria(e.target.value)}
                      placeholder="Criteria (optional)"
                      className="input-field text-sm"
                    />
                  </div>
                  <button
                    onClick={() => addTestCase({ input: tcInput, expected_output: tcExpected || undefined, criteria: tcCriteria || undefined })}
                    disabled={!tcInput.trim() || addingTc}
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
                  >
                    {addingTc ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <PlusIcon size={12} />}
                    Add test case
                  </button>
                </div>
              </div>

              {/* Runs */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">Runs ({runList.length})</p>
                  <button
                    onClick={() => createRun({ suite_id: selectedSuite.id, agent_id: runAgentId || undefined, model_name: runModel || undefined })}
                    disabled={creatingRun}
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
                  >
                    {creatingRun ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <PlayIcon size={12} />}
                    New Run
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                  <select value={runAgentId} onChange={(e) => setRunAgentId(e.target.value)} className="input-field text-sm">
                    <option value="">Agent: none</option>
                    {agentList.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                  <input
                    value={runModel}
                    onChange={(e) => setRunModel(e.target.value)}
                    placeholder="Model (optional, e.g. gpt-4o)"
                    className="input-field text-sm"
                  />
                </div>

                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {runList.length === 0 ? (
                    <p className="text-xs text-surface-600 py-4 text-center">No runs yet — click “New Run”</p>
                  ) : (
                    runList.map((run) => (
                      <div
                        key={run.id}
                        onClick={() => { setSelectedRunId(run.id); setRegression(null) }}
                        className={cn(
                          'p-3 rounded-xl cursor-pointer transition-all border',
                          selectedRunId === run.id
                            ? 'bg-primary-500/10 border-primary-500/30'
                            : 'bg-surface-800/50 border-transparent hover:bg-surface-800',
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className={cn('chip text-[10px]', statusColor[run.status] || 'bg-surface-800 text-surface-400')}>{run.status}</span>
                          <span className="text-[11px] text-surface-600 font-mono">{run.id.slice(0, 8)}</span>
                        </div>
                        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-surface-500">
                          {run.summary && <span>Pass rate: <span className="text-surface-300">{run.summary.pass_rate}%</span></span>}
                          {run.summary && <span>Avg score: <span className="text-surface-300">{run.summary.avg_score}</span></span>}
                          <span>{run.results?.length || 0} results</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Run detail */}
      {selectedSuite && selectedRun && (
        <div className="glass-panel p-5 space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 className="font-medium flex items-center gap-2">
                <PlayIcon size={14} className="text-primary-400" />
                Run {selectedRun.id.slice(0, 8)}
                <span className={cn('chip text-[10px]', statusColor[selectedRun.status] || 'bg-surface-800 text-surface-400')}>{selectedRun.status}</span>
              </h3>
              <p className="text-[11px] text-surface-500 mt-0.5">Created {fmtDate(selectedRun.created_at)}{selectedRun.agent_id && ` · agent ${selectedRun.agent_id.slice(0, 8)}`}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => executeRun()}
                disabled={executingRun || selectedRun.status === 'completed'}
                className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
                title="Run every test case against the agent or model and LLM-judge the outputs"
              >
                {executingRun ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <RocketIcon size={12} />}
                {executingRun ? 'Running…' : 'Auto-run'}
              </button>
              <button
                onClick={() => checkRegression()}
                disabled={checkingRegression || selectedRun.status !== 'completed'}
                className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
              >
                {checkingRegression ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <RefreshCwIcon size={12} />}
                Check regression
              </button>
              <button
                onClick={() => completeRun()}
                disabled={completing || selectedRun.status === 'completed'}
                className={cn('text-xs py-1.5 px-3 flex items-center gap-1 rounded-xl transition-all', selectedRun.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'btn-primary')}
              >
                {completing ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <CheckIcon size={12} />}
                {selectedRun.status === 'completed' ? 'Completed' : 'Complete run'}
              </button>
            </div>
          </div>

          {/* Summary */}
          {selectedRun.summary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                <p className="text-[11px] text-surface-500">Pass rate</p>
                <p className="text-lg font-bold text-emerald-400">{selectedRun.summary.pass_rate}%</p>
              </div>
              <div className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                <p className="text-[11px] text-surface-500">Avg score</p>
                <p className="text-lg font-bold text-surface-100">{selectedRun.summary.avg_score}</p>
              </div>
              <div className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                <p className="text-[11px] text-surface-500">Passed</p>
                <p className="text-lg font-bold text-surface-100">{selectedRun.summary.passed} / {selectedRun.summary.total}</p>
              </div>
              <div className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                <p className="text-[11px] text-surface-500">Score range</p>
                <p className="text-lg font-bold text-surface-100">{selectedRun.summary.min_score} – {selectedRun.summary.max_score}</p>
              </div>
            </div>
          )}

          {/* Regression banner */}
          {regression && (
            <div className={cn(
              'flex items-start gap-2 p-3 rounded-xl border',
              regression.regression_detected
                ? 'bg-red-500/10 border-red-500/20 text-red-300'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300',
            )}>
              {regression.regression_detected ? <AlertTriangleIcon size={16} className="flex-shrink-0 mt-0.5" /> : <CheckCircleIcon size={16} className="flex-shrink-0 mt-0.5" />}
              <div>
                <p className="text-sm font-medium">{regression.message}</p>
                {regression.previous_pass_rate != null && (
                  <p className="text-xs mt-0.5 opacity-80">
                    Previous run pass rate: {regression.previous_pass_rate}% · current: {regression.current_pass_rate}% · threshold {regression.threshold}%
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Results */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">Results ({selectedRun.results?.length || 0})</p>
              <button
                onClick={() => setShowRecordResult(!showRecordResult)}
                className={cn('text-xs px-3 py-1.5 rounded-xl flex items-center gap-1 transition-all', showRecordResult ? 'bg-surface-800 text-surface-300' : 'btn-secondary')}
              >
                {showRecordResult ? <XIcon size={12} /> : <PlusIcon size={12} />}
                {showRecordResult ? 'Close' : 'Record result'}
              </button>
            </div>

            {showRecordResult && (
              <div className="space-y-2 mb-4 p-4 rounded-xl bg-surface-800/40 border border-surface-700/30">
                <textarea
                  value={resInput}
                  onChange={(e) => setResInput(e.target.value)}
                  placeholder="Input"
                  className="input-field font-mono text-sm min-h-[50px] resize-y"
                  rows={2}
                />
                <textarea
                  value={resOutput}
                  onChange={(e) => setResOutput(e.target.value)}
                  placeholder="Actual output"
                  className="input-field font-mono text-sm min-h-[50px] resize-y"
                  rows={2}
                />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={resScore}
                    onChange={(e) => setResScore(e.target.value)}
                    placeholder="Score 0.0 – 1.0"
                    className="input-field text-sm"
                  />
                  <input
                    value={resReasoning}
                    onChange={(e) => setResReasoning(e.target.value)}
                    placeholder="Judge reasoning (optional)"
                    className="input-field text-sm"
                  />
                </div>
                <button
                  onClick={() => recordResult({
                    test_case_id: 'manual',
                    input: resInput,
                    actual_output: resOutput,
                    score: Number(resScore) || 0,
                    judge_reasoning: resReasoning || undefined,
                  })}
                  disabled={!resInput.trim() || !resOutput.trim() || recording}
                  className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1"
                >
                  {recording ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <CheckIcon size={12} />}
                  Record
                </button>
              </div>
            )}

            <div className="space-y-2 max-h-[320px] overflow-y-auto">
              {(selectedRun.results || []).length === 0 ? (
                <p className="text-xs text-surface-600 py-4 text-center">No results recorded for this run</p>
              ) : (
                selectedRun.results.map((res) => (
                  <div key={res.id} className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {res.passed ? (
                          <CheckCircleIcon size={14} className="text-emerald-400" />
                        ) : (
                          <XCircleIcon size={14} className="text-red-400" />
                        )}
                        <span className="text-xs font-mono text-surface-400">{res.test_case_id.slice(0, 8)}</span>
                      </div>
                      <span className={cn('chip text-[10px]', res.score >= 0.7 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400')}>
                        {Math.round(res.score * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-surface-400 mt-1.5 line-clamp-2">{res.input}</p>
                    <p className="text-xs text-surface-300 mt-1 line-clamp-2"><span className="text-surface-500">Output:</span> {res.actual_output}</p>
                    {res.judge_reasoning && <p className="text-[11px] text-surface-500 mt-1 italic line-clamp-2">{res.judge_reasoning}</p>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
