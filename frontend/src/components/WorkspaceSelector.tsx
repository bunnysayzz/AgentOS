import { useQuery } from '@tanstack/react-query'
import { CheckIcon, ChevronDownIcon } from '@/components/Icons'
import { useState } from 'react'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { cn } from '@/utils/cn'

export default function WorkspaceSelector() {
  const [open, setOpen] = useState(false)
  const { selectedWorkspaceId, selectedWorkspaceName, setSelectedWorkspace } = useWorkspaceStore()

  const { data: workspaces } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.get('/workspaces/').then((r) => r.data),
  })

  const list: { id: string; name: string }[] = Array.isArray(workspaces) ? workspaces : []

  if (list.length === 0) return null

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-800 border border-surface-700/50 hover:border-surface-600 text-sm text-surface-200 transition-all duration-200"
      >
        <span className="truncate max-w-[160px]">
          {selectedWorkspaceName || 'Select workspace'}
        </span>
        <ChevronDownIcon size={14} className="text-surface-500 flex-shrink-0" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 w-56 z-20 glass-panel p-1 shadow-xl">
            {list.map((ws) => (
              <button
                key={ws.id}
                onClick={() => {
                  setSelectedWorkspace(ws.id, ws.name)
                  setOpen(false)
                }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-150',
                  selectedWorkspaceId === ws.id
                    ? 'bg-primary-500/10 text-primary-400'
                    : 'text-surface-300 hover:bg-surface-800',
                )}
              >
                <span className="flex-1 text-left truncate">{ws.name}</span>
                {selectedWorkspaceId === ws.id && <CheckIcon size={14} className="flex-shrink-0" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
