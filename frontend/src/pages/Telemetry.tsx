import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ActivityIcon, AlertTriangleIcon, BarChart3Icon, ClockIcon, DollarSignIcon, ListOrderedIcon, PlusIcon, SendIcon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import { cn } from '@/utils/cn'

interface Event { id: string; event_name: string; event_type: string; severity: string; duration_ms?: number; cost_usd?: number; created_at: string }
interface AuditLog { id: string; action: string; resource_type: string; resource_id?: string; created_at: string }

export default function Telemetry() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [tab, setTab] = useState<'stats' | 'events' | 'audit'>('stats')
  const [sevFilter, setSevFilter] = useState('')
  const [showCreateEvent, setShowCreateEvent] = useState(false)
  const [eventForm, setEventForm] = useState({ event_name: '', event_type: 'custom', severity: 'info', body: '' })

  const { mutate: createEvent, isPending: creatingEvent } = useMutation({
    mutationFn: () => api.post(`/workspaces/${wsId}/events`, {
      event_name: eventForm.event_name,
      event_type: eventForm.event_type,
      severity: eventForm.severity,
      body: eventForm.body ? { message: eventForm.body } : undefined,
    }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['telemetry-events', wsId] }); qc.invalidateQueries({ queryKey: ['telemetry-stats', wsId] }); setShowCreateEvent(false); setEventForm({ event_name: '', event_type: 'custom', severity: 'info', body: '' }) },
  })

  const { data: stats } = useQuery({
    queryKey: ['telemetry-stats', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/events/stats`, { params: { days: 7 } }).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: events } = useQuery({
    queryKey: ['telemetry-events', wsId, sevFilter],
    queryFn: () => api.get(`/workspaces/${wsId}/events`, { params: { severity: sevFilter || undefined, limit: 50 } }).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: auditLogs } = useQuery({
    queryKey: ['audit-logs', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/audit-logs`, { params: { limit: 50 } }).then((r) => r.data),
    enabled: !!wsId,
  })

  const eventList: Event[] = Array.isArray(events) ? events : []
  const auditList: AuditLog[] = Array.isArray(auditLogs) ? auditLogs : []

  if (!wsId) return <div className="space-y-4"><h1 className="text-2xl font-bold">Telemetry</h1><WorkspaceSelector /><p className="text-surface-400 text-sm mt-2">Select a workspace to view telemetry</p></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Telemetry & Observability</h1></div>
        <WorkspaceSelector />
      </div>

      <div className="flex gap-1 p-1 rounded-xl bg-surface-800/50 w-fit">
        {(['stats', 'events', 'audit'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn('px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all', tab === t ? 'bg-surface-700 text-white' : 'text-surface-400 hover:text-surface-200')}>
            {t === 'stats' && <BarChart3Icon size={14} className="inline mr-1.5" />}
            {t === 'events' && <ActivityIcon size={14} className="inline mr-1.5" />}
            {t === 'audit' && <ListOrderedIcon size={14} className="inline mr-1.5" />}
            {t}
          </button>
        ))}
      </div>

      {tab === 'stats' && (
        <div>
          {stats ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="card"><ActivityIcon size={18} className="text-primary-400 mb-2" /><p className="text-2xl font-bold">{stats.total_events}</p><p className="text-xs text-surface-500">Events (7d)</p></div>
                <div className="card"><AlertTriangleIcon size={18} className="text-red-400 mb-2" /><p className="text-2xl font-bold">{stats.errors}</p><p className="text-xs text-surface-500">Errors (7d)</p></div>
                <div className="card"><DollarSignIcon size={18} className="text-emerald-400 mb-2" /><p className="text-2xl font-bold">${stats.total_cost_usd?.toFixed(4) || '0'}</p><p className="text-xs text-surface-500">Total Cost (7d)</p></div>
                <div className="card"><ClockIcon size={18} className="text-amber-400 mb-2" /><p className="text-2xl font-bold">{stats.avg_duration_ms?.toFixed(0) || '0'}ms</p><p className="text-xs text-surface-500">Avg Duration</p></div>
              </div>

              {stats.events_by_type && Object.keys(stats.events_by_type).length > 0 && (
                <div className="glass-panel p-5">
                  <h3 className="font-medium mb-3">Events by Type</h3>
                  <div className="space-y-2">
                    {Object.entries(stats.events_by_type as Record<string, number>).map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between py-1.5">
                        <span className="text-sm text-surface-300">{type}</span>
                        <div className="flex items-center gap-3">
                          <div className="w-24 h-2 rounded-full bg-surface-700 overflow-hidden">
                            <div className="h-full rounded-full bg-primary-500" style={{ width: `${Math.min(100, (count / Math.max(...Object.values(stats.events_by_type as Record<string, number>))) * 100)}%` }} />
                          </div>
                          <span className="text-sm font-medium text-surface-300 w-8 text-right">{count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="glass-panel p-12 text-center"><BarChart3Icon className="w-12 h-12 text-surface-600 mx-auto mb-3" /><h3 className="text-lg font-medium text-surface-400">No stats yet</h3></div>
          )}
        </div>
      )}

      {tab === 'events' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {['', 'info', 'warning', 'error', 'critical'].map((s) => (
                <button key={s} onClick={() => setSevFilter(s)} className={cn('chip cursor-pointer hover:bg-surface-700 transition-colors', sevFilter === s && 'bg-primary-500/20 text-primary-400 border-primary-500/30')}>
                  {s || 'All'}
                </button>
              ))}
            </div>
            <button onClick={() => setShowCreateEvent(true)} className="btn-primary flex items-center gap-1.5 text-xs py-1.5 px-3"><PlusIcon size={12} />Log Event</button>
          </div>
          <div className="space-y-2">
            {eventList.length === 0 ? (
              <div className="glass-panel p-12 text-center"><ActivityIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" /><h3 className="text-lg font-medium text-surface-400">No events</h3></div>
            ) : eventList.map((e) => (
              <div key={e.id} className="card flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{e.event_name}</p>
                  <p className="text-xs text-surface-500">{e.event_type}</p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className={cn('chip text-[10px]', e.severity === 'error' || e.severity === 'critical' ? 'text-red-400 bg-red-500/10' : e.severity === 'warning' ? 'text-amber-400 bg-amber-500/10' : 'text-surface-400')}>{e.severity}</span>
                  {e.duration_ms && <span className="text-xs text-surface-500">{e.duration_ms}ms</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Create Event Modal */}
          {showCreateEvent && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCreateEvent(false)}>
              <div className="w-full max-w-md glass-panel p-6" onClick={(e) => e.stopPropagation()}>
                <h3 className="font-semibold mb-4">Log Custom Event</h3>
                <div className="space-y-4">
                  <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Event Name</label><input type="text" placeholder="user.login" value={eventForm.event_name} onChange={(e) => setEventForm({ ...eventForm, event_name: e.target.value })} className="input-field" /></div>
                  <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Type</label><input type="text" placeholder="custom" value={eventForm.event_type} onChange={(e) => setEventForm({ ...eventForm, event_type: e.target.value })} className="input-field" /></div>
                  <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Severity</label>
                    <select value={eventForm.severity} onChange={(e) => setEventForm({ ...eventForm, severity: e.target.value })} className="input-field">
                      <option value="info">Info</option><option value="warning">Warning</option><option value="error">Error</option><option value="critical">Critical</option>
                    </select>
                  </div>
                  <div><label className="block text-sm font-medium text-surface-300 mb-1.5">Body (message)</label><textarea value={eventForm.body} onChange={(e) => setEventForm({ ...eventForm, body: e.target.value })} className="input-field min-h-[60px] resize-none" rows={2} /></div>
                  <div className="flex gap-3 pt-2">
                    <button onClick={() => setShowCreateEvent(false)} className="btn-secondary flex-1">Cancel</button>
                    <button onClick={() => createEvent()} disabled={!eventForm.event_name.trim() || creatingEvent} className="btn-primary flex-1 flex items-center justify-center gap-2">
                      {creatingEvent ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><SendIcon size={14} />Log</>}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'audit' && (
        <div className="space-y-2">
          {auditList.length === 0 ? (
            <div className="glass-panel p-12 text-center"><ListOrderedIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" /><h3 className="text-lg font-medium text-surface-400">No audit logs</h3></div>
          ) : auditList.map((l) => (
            <div key={l.id} className="card flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <span className={cn('chip text-[10px] uppercase', l.action === 'delete' ? 'text-red-400 bg-red-500/10' : l.action === 'create' ? 'text-emerald-400 bg-emerald-500/10' : 'text-primary-400 bg-primary-500/10')}>{l.action}</span>
                <span className="text-sm text-surface-300 truncate">{l.resource_type}</span>
                {l.resource_id && <span className="text-xs text-surface-600 font-mono truncate max-w-[100px]">{l.resource_id.slice(0, 8)}...</span>}
              </div>
              <span className="text-xs text-surface-500 flex-shrink-0">{l.created_at?.slice(0, 10)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
