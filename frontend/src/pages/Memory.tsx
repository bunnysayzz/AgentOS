import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { LayersIcon, MessageSquareIcon, SearchIcon, Trash2Icon } from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import WorkspaceRequired from '@/components/WorkspaceRequired'
import { confirm } from '@/components/ConfirmDialog'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface Entry { id: string; session_id: string; role: string; content: string; memory_type: string; importance: number; created_at: string }

export default function Memory() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [sessionId, setSessionId] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [newEntry, setNewEntry] = useState('')

  const { data: entries, isLoading } = useQuery({
    queryKey: ['session-memory', wsId, sessionId],
    queryFn: () => api.get(`/workspaces/${wsId}/memory/sessions/${sessionId}`).then((r) => r.data),
    enabled: !!wsId && !!sessionId,
  })

  const { data: searchResults, isLoading: searching } = useQuery({
    queryKey: ['memory-search', wsId, searchTerm],
    queryFn: () => api.get(`/workspaces/${wsId}/memory/search`, { params: { q: searchTerm, limit: 50 } }).then((r) => r.data),
    enabled: !!wsId && !!searchTerm,
  })

  const { mutate: clearSession } = useMutation({
    mutationFn: () => api.delete(`/workspaces/${wsId}/memory/sessions/${sessionId}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['session-memory', wsId, sessionId] }); setSessionId('') },
  })

  const { mutate: createEntry, isPending: creatingEntry } = useMutation({
    mutationFn: (content: string) => api.post(`/workspaces/${wsId}/memory`, {
      session_id: sessionId, role: 'user', content, memory_type: 'conversation'
    }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['session-memory', wsId, sessionId] }); setNewEntry('') },
    onError: (err: any) => { const msg = err.response?.data?.detail || 'Failed to save entry'; console.error(msg); },
  })

  const { mutate: consolidate, isPending: consolidating } = useMutation({
    mutationFn: () => api.post(`/workspaces/${wsId}/memory/consolidate`, { session_id: sessionId, max_entries: 50 }).then((r) => r.data),
    onSuccess: (_data: any) => { qc.invalidateQueries({ queryKey: ['session-memory', wsId, sessionId] }); toast.success('Memory consolidated', 'Old entries have been compressed.') },
  })

  const entryList: Entry[] = Array.isArray(entries) ? entries : []
  const searchList: Entry[] = Array.isArray(searchResults) ? searchResults : []

  if (!wsId) return <WorkspaceRequired title="Memory" description="Select a workspace to browse memory" />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Memory</h1><p className="text-surface-400 text-sm mt-1">Conversation & session memory</p></div>
        <WorkspaceSelector />
      </div>

      {/* SearchIcon */}
      <div className="glass-panel p-5">
        <h3 className="font-medium mb-3 flex items-center gap-2"><SearchIcon size={16} /> Search Memory</h3>
        <div className="flex gap-2">
          <input type="text" placeholder="Search keywords..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="input-field flex-1"
            onKeyDown={(e) => { if (e.key === 'Enter' && searchQuery.trim()) setSearchTerm(searchQuery.trim()) }} />
          <button onClick={() => { if (searchQuery.trim()) setSearchTerm(searchQuery.trim()) }} className="btn-primary">Search</button>
        </div>
        {searching && <div className="text-sm text-surface-500 mt-2">Searching...</div>}
        {searchTerm && searchList.length > 0 && (
          <div className="mt-4 space-y-2 max-h-60 overflow-y-auto">
            {searchList.map((e) => (
              <div key={e.id} className="py-2 px-3 rounded-xl bg-surface-800/50">
                <div className="flex items-center gap-2 mb-1"><span className={cn('chip text-[10px]', e.role === 'assistant' ? 'text-emerald-400' : 'text-primary-400')}>{e.role}</span><span className="text-[10px] text-surface-500">{e.memory_type}</span></div>
                <p className="text-sm text-surface-300 line-clamp-2">{e.content}</p>
              </div>
            ))}
          </div>
        )}
        {searchTerm && searchList.length === 0 && !searching && <p className="text-sm text-surface-500 mt-2">No results for "{searchTerm}"</p>}
      </div>

      {/* Session browser */}
      <div className="glass-panel p-5">
        <h3 className="font-medium mb-3 flex items-center gap-2"><MessageSquareIcon size={16} /> Session Memory</h3>          <div className="flex gap-2 mb-4">
          <input type="text" placeholder="Enter session ID..." value={sessionId} onChange={(e) => setSessionId(e.target.value)} className="input-field flex-1" />
          {sessionId && (
            <>
              <button onClick={() => consolidate()} disabled={consolidating} className="btn-secondary flex items-center gap-1 text-xs">
                {consolidating ? <div className="w-3 h-3 border-2 border-surface-400/30 border-t-surface-400 rounded-full animate-spin" /> : <LayersIcon size={14} />}
                Compress
              </button>
              <button onClick={() => confirm.danger('Clear Session?','This will permanently delete all memory entries for this session.',async () => clearSession())} className="btn-secondary flex items-center gap-1 text-red-400 hover:text-red-300"><Trash2Icon size={14} />Clear</button>
            </>
          )}
        </div>
        {sessionId && (
          <div className="flex gap-2 mb-4">
            <input type="text" placeholder="Type a message to add to memory..." value={newEntry} onChange={(e) => setNewEntry(e.target.value)} className="input-field flex-1"
              onKeyDown={(e) => { if (e.key === 'Enter' && newEntry.trim() && sessionId) createEntry(newEntry.trim()) }} />
            <button onClick={() => { if (newEntry.trim() && sessionId) createEntry(newEntry.trim()) }} disabled={creatingEntry || !newEntry.trim()} className="btn-primary flex items-center gap-1 text-xs">
              {creatingEntry ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <MessageSquareIcon size={14} />}
              Add
            </button>
          </div>
        )}
        {isLoading ? (
          <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-surface-800 rounded-xl animate-pulse" />)}</div>
        ) : sessionId && entryList.length === 0 ? (
          <p className="text-sm text-surface-500 py-4 text-center">No memory entries for this session</p>
        ) : (
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {entryList.map((e) => (
              <div key={e.id} className={cn('py-3 px-4 rounded-xl', e.role === 'assistant' ? 'bg-primary-500/5 border border-primary-500/10' : 'bg-surface-800/50')}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn('chip text-[10px]', e.role === 'assistant' ? 'text-emerald-400 bg-emerald-500/10' : 'text-primary-400 bg-primary-500/10')}>{e.role}</span>
                  <span className="text-[10px] text-surface-500">{e.memory_type}</span>
                  {e.importance > 0 && <span className="text-[10px] text-amber-400">★ {e.importance}</span>}
                </div>
                <p className="text-sm text-surface-300 whitespace-pre-wrap">{e.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
