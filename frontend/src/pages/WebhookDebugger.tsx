import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  WebhookIcon, PlayIcon, RefreshCwIcon, EyeIcon, CopyIcon, CheckIcon,
  ArrowRightIcon, ClockIcon, AlertTriangleIcon, SendIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface WebhookLog {
  id: string
  webhook_id: string
  direction: 'inbound' | 'outbound'
  method: string
  url: string
  headers: Record<string, string>
  body: string | null
  status_code: number | null
  response_body: string | null
  duration_ms: number | null
  error: string | null
  created_at: string
}

export default function WebhookDebugger() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [testUrl, setTestUrl] = useState('')
  const [testMethod, setTestMethod] = useState('POST')
  const [testBody, setTestBody] = useState('{\n  "event": "test",\n  "data": {}\n}')
  const [testHeaders, setTestHeaders] = useState('{\n  "Content-Type": "application/json"\n}')
  const [selectedLog, setSelectedLog] = useState<WebhookLog | null>(null)
  const [showTestPanel, setShowTestPanel] = useState(false)

  const { data: logs } = useQuery({
    queryKey: ['webhook-logs', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/webhook-debugger/logs`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { mutate: testWebhook, isPending: testing } = useMutation({
    mutationFn: (data: { url: string; method: string; body: string; headers: string }) =>
      api.post(`/workspaces/${wsId}/webhook-debugger/test`, {
        url: data.url,
        method: data.method,
        body: data.body,
        headers: JSON.parse(data.headers || '{}'),
      }).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['webhook-logs', wsId] })
      setSelectedLog(data)
      toast.success('Webhook sent', `Status: ${data.status_code || 'error'}`)
    },
    onError: (err: any) => toast.error('Test failed', err?.response?.data?.detail),
  })

  const { mutate: retryWebhook, isPending: retrying } = useMutation({
    mutationFn: (logId: string) =>
      api.post(`/workspaces/${wsId}/webhook-debugger/retry/${logId}`).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['webhook-logs', wsId] })
      setSelectedLog(data)
      toast.success('Webhook retried', `Status: ${data.status_code || 'error'}`)
    },
    onError: (err: any) => toast.error('Retry failed', err?.response?.data?.detail),
  })

  const logList: WebhookLog[] = Array.isArray(logs) ? logs : []
  const [copied, setCopied] = useState<string | null>(null)

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(id)
      setTimeout(() => setCopied(null), 1500)
    })
  }

  const formatJson = (str: string | null) => {
    if (!str) return null
    try {
      return JSON.stringify(JSON.parse(str), null, 2)
    } catch {
      return str
    }
  }

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Webhook Debugger</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace</p></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Webhook Debugger</h1>
          <p className="text-surface-400 text-sm mt-1">Test, inspect, and retry webhook calls</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          <button
            onClick={() => setShowTestPanel(!showTestPanel)}
            className={cn('flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all', showTestPanel ? 'bg-emerald-500 text-white' : 'btn-primary')}
          >
            <SendIcon size={16} />
            {showTestPanel ? 'Close Tester' : 'Test Webhook'}
          </button>
        </div>
      </div>

      {/* Test Panel */}
      {showTestPanel && (
        <div className="glass-panel p-5 space-y-4">
          <h3 className="font-medium flex items-center gap-2">
            <SendIcon size={16} className="text-emerald-400" />
            Test Webhook
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="md:col-span-3">
              <label className="block text-sm font-medium text-surface-300 mb-1.5">URL</label>
              <input
                type="url"
                placeholder="https://example.com/webhook"
                value={testUrl}
                onChange={(e) => setTestUrl(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Method</label>
              <select
                value={testMethod}
                onChange={(e) => setTestMethod(e.target.value)}
                className="input-field"
              >
                <option value="POST">POST</option>
                <option value="GET">GET</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Headers (JSON)</label>
              <textarea
                value={testHeaders}
                onChange={(e) => setTestHeaders(e.target.value)}
                className="input-field font-mono text-sm min-h-[100px] resize-y"
                rows={4}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Body</label>
              <textarea
                value={testBody}
                onChange={(e) => setTestBody(e.target.value)}
                className="input-field font-mono text-sm min-h-[100px] resize-y"
                rows={4}
              />
            </div>
          </div>

          <button
            onClick={() => testWebhook({ url: testUrl, method: testMethod, body: testBody, headers: testHeaders })}
            disabled={!testUrl || testing}
            className="btn-primary flex items-center gap-2"
          >
            {testing ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <PlayIcon size={16} />}
            Send Test
          </button>
        </div>
      )}

      {/* Logs + Detail Split */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Logs List */}
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2">
              <WebhookIcon size={16} className="text-primary-400" />
              Recent Logs ({logList.length})
            </h3>
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ['webhook-logs', wsId] })}
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all"
            >
              <RefreshCwIcon size={14} />
            </button>
          </div>

          {logList.length === 0 ? (
            <div className="py-8 text-center">
              <WebhookIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">No webhook logs yet</p>
              <p className="text-xs text-surface-600 mt-1">Send a test webhook to see logs here</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {logList.map((log) => (
                <div
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  className={cn(
                    'p-3 rounded-xl cursor-pointer transition-all border',
                    selectedLog?.id === log.id
                      ? 'bg-primary-500/10 border-primary-500/30'
                      : 'bg-surface-800/50 border-transparent hover:bg-surface-800',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'chip text-[10px] font-mono',
                        log.direction === 'inbound' ? 'bg-blue-500/10 text-blue-400' : 'bg-emerald-500/10 text-emerald-400',
                      )}>
                        {log.direction === 'inbound' ? 'IN' : 'OUT'}
                      </span>
                      <span className="text-xs font-mono text-surface-400">{log.method}</span>
                      <ArrowRightIcon size={10} className="text-surface-600" />
                      {log.status_code ? (
                        <span className={cn(
                          'text-xs font-mono',
                          log.status_code >= 200 && log.status_code < 300 ? 'text-emerald-400' :
                          log.status_code >= 400 ? 'text-red-400' : 'text-amber-400',
                        )}>
                          {log.status_code}
                        </span>
                      ) : (
                        <span className="text-xs text-red-400">ERR</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {log.duration_ms != null && (
                        <span className="text-xs text-surface-500 flex items-center gap-1">
                          <ClockIcon size={10} />{log.duration_ms}ms
                        </span>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          retryWebhook(log.id)
                        }}
                        disabled={retrying}
                        className="p-1 rounded text-surface-500 hover:text-primary-400 hover:bg-surface-800 transition-all"
                        title="Retry"
                      >
                        <RefreshCwIcon size={12} />
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-surface-500 mt-1 truncate font-mono">{log.url}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <div className="glass-panel p-5">
          {selectedLog ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium flex items-center gap-2">
                  <EyeIcon size={16} className="text-primary-400" />
                  Request Detail
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => retryWebhook(selectedLog.id)}
                    disabled={retrying}
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
                  >
                    <RefreshCwIcon size={12} />
                    Retry
                  </button>
                  <button
                    onClick={() => copyToClipboard(JSON.stringify(selectedLog, null, 2), 'full')}
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
                  >
                    {copied === 'full' ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
                    {copied === 'full' ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>

              {/* Request Info */}
              <div className="p-3 rounded-xl bg-surface-800/50 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="chip text-[10px]">{selectedLog.method}</span>
                  <span className="text-xs font-mono text-surface-300 break-all">{selectedLog.url}</span>
                </div>
                {selectedLog.duration_ms != null && (
                  <p className="text-xs text-surface-500">
                    <ClockIcon size={10} className="inline mr-1" />
                    {selectedLog.duration_ms}ms
                  </p>
                )}
                {selectedLog.error && (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                    <AlertTriangleIcon size={12} className="text-red-400" />
                    <p className="text-xs text-red-300">{selectedLog.error}</p>
                  </div>
                )}
              </div>

              {/* Headers */}
              {selectedLog.headers && Object.keys(selectedLog.headers).length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">Headers</p>
                    <button
                      onClick={() => copyToClipboard(JSON.stringify(selectedLog.headers, null, 2), 'headers')}
                      className="text-xs text-surface-500 hover:text-surface-300"
                    >
                      {copied === 'headers' ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <pre className="p-3 rounded-xl bg-surface-900/50 border border-surface-700/30 text-xs text-surface-300 overflow-x-auto font-mono">
                    {JSON.stringify(selectedLog.headers, null, 2)}
                  </pre>
                </div>
              )}

              {/* Request Body */}
              {selectedLog.body && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">Request Body</p>
                    <button
                      onClick={() => copyToClipboard(selectedLog.body || '', 'reqbody')}
                      className="text-xs text-surface-500 hover:text-surface-300"
                    >
                      {copied === 'reqbody' ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <pre className="p-3 rounded-xl bg-surface-900/50 border border-surface-700/30 text-xs text-surface-300 overflow-x-auto font-mono whitespace-pre-wrap">
                    {formatJson(selectedLog.body)}
                  </pre>
                </div>
              )}

              {/* Response */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">
                    Response {selectedLog.status_code && `(${selectedLog.status_code})`}
                  </p>
                  {selectedLog.response_body && (
                    <button
                      onClick={() => copyToClipboard(selectedLog.response_body || '', 'respbody')}
                      className="text-xs text-surface-500 hover:text-surface-300"
                    >
                      {copied === 'respbody' ? 'Copied' : 'Copy'}
                    </button>
                  )}
                </div>
                <pre className="p-3 rounded-xl bg-surface-900/50 border border-surface-700/30 text-xs text-surface-300 overflow-x-auto font-mono whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                  {selectedLog.response_body ? formatJson(selectedLog.response_body) : 'No response body'}
                </pre>
              </div>
            </div>
          ) : (
            <div className="py-12 text-center">
              <EyeIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
              <p className="text-surface-500 text-sm">Select a log to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
