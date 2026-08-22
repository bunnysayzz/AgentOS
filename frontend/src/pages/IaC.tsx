import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ServerIcon, DownloadIcon, CopyIcon, CheckIcon, RefreshCwIcon, SendIcon,
  CheckCircleIcon, XCircleIcon, AlertTriangleIcon, CodeIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface IaCManifest {
  agentos_version: string
  exported_at: string
  workspace_id: string
  resources: {
    agents: unknown[]
    workflows: unknown[]
    prompts: unknown[]
    tools: unknown[]
  }
  summary: {
    agents: number
    workflows: number
    prompts: number
    tools: number
  }
}

interface ImportResult {
  success: boolean
  dry_run?: boolean
  would_import?: { agents: number; workflows: number; prompts: number; tools: number }
  imported?: { agents: number; workflows: number; prompts: number; tools: number }
  errors?: string[]
  error?: string
}

type ImportTab = 'json' | 'yaml'

const DEFAULT_JSON = `{
  "agentos_version": "1.0",
  "resources": {
    "agents": [],
    "workflows": [],
    "prompts": [],
    "tools": []
  }
}`

function fmtDate(iso?: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function IaC() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId

  const [tab, setTab] = useState<ImportTab>('json')
  const [manifestText, setManifestText] = useState(DEFAULT_JSON)
  const [dryRun, setDryRun] = useState(true)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: manifest } = useQuery({
    queryKey: ['iac-export', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/iac/export/json`).then((r) => r.data),
    enabled: !!wsId,
  })

  const exportJson = (manifest || null) as IaCManifest | null

  const { mutate: importJson, isPending: importingJson } = useMutation({
    mutationFn: (d: { manifest: unknown; dry_run: boolean }) =>
      api.post(`/workspaces/${wsId}/iac/import`, d).then((r) => r.data),
    onSuccess: (data: ImportResult) => {
      setImportResult(data)
      if (data.dry_run) {
        toast.success('Dry run complete', 'Nothing was imported')
      } else if (data.success) {
        toast.success('Manifest imported')
        qc.invalidateQueries({ queryKey: ['iac-export', wsId] })
      } else {
        toast.error('Import had errors', data.error || 'See result below')
      }
    },
    onError: (err: any) => toast.error('Import failed', err?.response?.data?.detail),
  })

  const { mutate: importYaml, isPending: importingYaml } = useMutation({
    mutationFn: (body: string) =>
      api.post(`/workspaces/${wsId}/iac/import/yaml`, body, { headers: { 'Content-Type': 'text/plain' } }).then((r) => r.data),
    onSuccess: (data: ImportResult) => {
      setImportResult(data)
      if (data.dry_run) {
        toast.success('Dry run complete', 'Nothing was imported')
      } else if (data.success) {
        toast.success('Manifest imported')
        qc.invalidateQueries({ queryKey: ['iac-export', wsId] })
      } else {
        toast.error('Import had errors', data.error || 'See result below')
      }
    },
    onError: (err: any) => toast.error('Import failed', err?.response?.data?.detail),
  })

  const handleImport = () => {
    setImportResult(null)
    if (tab === 'json') {
      try {
        const manifest = JSON.parse(manifestText)
        importJson({ manifest, dry_run: dryRun })
      } catch {
        toast.error('Invalid JSON', 'Check the manifest syntax')
      }
    } else {
      importYaml(manifestText)
    }
  }

  const copyExport = () => {
    if (!exportJson) return
    navigator.clipboard.writeText(JSON.stringify(exportJson, null, 2)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const downloadJson = () => {
    if (!exportJson) return
    const blob = new Blob([JSON.stringify(exportJson, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `agentos-${(wsId || '').slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadYaml = async () => {
    try {
      const res = await api.get(`/workspaces/${wsId}/iac/export?format=yaml`, { responseType: 'text' })
      const blob = new Blob([res.data], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `agentos-${(wsId || '').slice(0, 8)}.yaml`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Export failed', 'Could not fetch the YAML manifest')
    }
  }

  if (!wsId) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Infrastructure as Code</h1>
        <WorkspaceSelector />
        <p className="text-surface-400 text-sm mt-2">Select a workspace to export or import IaC manifests</p>
      </div>
    )
  }

  const summaryItems: { label: string; count: number }[] = exportJson
    ? [
        { label: 'Agents', count: exportJson.summary.agents },
        { label: 'Workflows', count: exportJson.summary.workflows },
        { label: 'Prompts', count: exportJson.summary.prompts },
        { label: 'Tools', count: exportJson.summary.tools },
      ]
    : []

  const imported = importResult?.imported
  const wouldImport = importResult?.would_import

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Infrastructure as Code</h1>
          <p className="text-surface-400 text-sm mt-1">Export workspace resources as manifests, or import them</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ['iac-export', wsId] })}
            className="p-2 rounded-xl text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all"
            title="Refresh"
          >
            <RefreshCwIcon size={16} />
          </button>
        </div>
      </div>

      {/* Export */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h3 className="font-medium flex items-center gap-2">
            <ServerIcon size={16} className="text-primary-400" />
            Export Workspace
          </h3>
          <div className="flex items-center gap-2">
            <button onClick={copyExport} disabled={!exportJson} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
              {copied ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
              {copied ? 'Copied' : 'Copy JSON'}
            </button>
            <button onClick={downloadJson} disabled={!exportJson} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
              <DownloadIcon size={12} />
              .json
            </button>
            <button onClick={downloadYaml} disabled={!exportJson} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
              <DownloadIcon size={12} />
              .yaml
            </button>
          </div>
        </div>

        {exportJson ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {summaryItems.map((item) => (
                <div key={item.label} className="p-3 rounded-xl bg-surface-800/50 border border-surface-700/30">
                  <p className="text-[11px] text-surface-500">{item.label}</p>
                  <p className="text-lg font-bold text-surface-100">{item.count}</p>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-surface-600">
              IaC version {exportJson.agentos_version} · exported {fmtDate(exportJson.exported_at)}
            </p>
            <pre className="p-4 rounded-xl bg-surface-900/50 border border-surface-700/30 text-xs text-surface-300 overflow-x-auto font-mono max-h-[360px] overflow-y-auto">
              {JSON.stringify(exportJson, null, 2)}
            </pre>
          </>
        ) : (
          <div className="py-8 text-center">
            <ServerIcon className="w-10 h-10 text-surface-600 mx-auto mb-2" />
            <p className="text-surface-500 text-sm">No resources to export, or export not yet loaded</p>
          </div>
        )}
      </div>

      {/* Import */}
      <div className="glass-panel p-5 space-y-4">
        <h3 className="font-medium flex items-center gap-2">
          <CodeIcon size={16} className="text-primary-400" />
          Import Manifest
        </h3>

        <div className="flex items-center gap-2">
          {(['json', 'yaml'] as ImportTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'px-3 py-1.5 rounded-xl text-xs font-medium transition-all',
                tab === t ? 'bg-primary-500/15 text-primary-300 border border-primary-500/30' : 'text-surface-500 hover:text-surface-300 border border-transparent',
              )}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>

        <textarea
          value={manifestText}
          onChange={(e) => setManifestText(e.target.value)}
          placeholder={tab === 'json' ? 'Paste an IaC JSON manifest…' : 'Paste an IaC YAML manifest…'}
          className="input-field font-mono text-sm min-h-[220px] resize-y"
          rows={10}
        />

        <div className="flex items-center gap-4 flex-wrap">
          <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="w-4 h-4 rounded border-surface-600 accent-primary-500"
            />
            Dry run (preview only, nothing imported)
          </label>
          <button
            onClick={handleImport}
            disabled={!manifestText.trim() || importingJson || importingYaml}
            className="btn-primary flex items-center gap-2"
          >
            {(importingJson || importingYaml) ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <SendIcon size={16} />
            )}
            Import
          </button>
        </div>

        {/* Import result */}
        {importResult && (
          <div className={cn(
            'p-4 rounded-xl border space-y-3',
            importResult.success
              ? 'bg-emerald-500/5 border-emerald-500/25'
              : 'bg-red-500/5 border-red-500/25',
          )}>
            <div className="flex items-center gap-2">
              {importResult.success ? (
                <CheckCircleIcon size={16} className="text-emerald-400 flex-shrink-0" />
              ) : (
                <XCircleIcon size={16} className="text-red-400 flex-shrink-0" />
              )}
              <p className={cn('text-sm font-medium', importResult.success ? 'text-emerald-300' : 'text-red-300')}>
                {importResult.success
                  ? importResult.dry_run ? 'Dry run preview ready' : 'Import complete'
                  : importResult.error || 'Import failed'}
              </p>
            </div>

            {importResult.dry_run && wouldImport && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {Object.entries(wouldImport).map(([k, v]) => (
                  <div key={k} className="p-2 rounded-lg bg-surface-900/50">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide">{k}</p>
                    <p className="text-sm font-bold text-surface-100 mt-0.5">{v}</p>
                  </div>
                ))}
              </div>
            )}

            {imported && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {Object.entries(imported).map(([k, v]) => (
                  <div key={k} className="p-2 rounded-lg bg-surface-900/50">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide">{k}</p>
                    <p className="text-sm font-bold text-surface-100 mt-0.5">{v}</p>
                  </div>
                ))}
              </div>
            )}

            {importResult.errors && importResult.errors.length > 0 && (
              <div className="space-y-1">
                {importResult.errors.map((e, i) => (
                  <p key={i} className="text-xs text-red-300 flex items-start gap-1.5">
                    <AlertTriangleIcon size={12} className="flex-shrink-0 mt-0.5" />
                    {e}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
