import WorkspaceSelector from '@/components/WorkspaceSelector'
import { LayersIcon } from '@/components/Icons'

interface WorkspaceRequiredProps {
  title: string
  description?: string
}

/**
 * Polished fallback for workspace-scoped pages when no workspace is selected:
 * a centered glass card with the workspace dropdown front and center, instead
 * of a bare heading + dropdown pair.
 */
export default function WorkspaceRequired({ title, description }: WorkspaceRequiredProps) {
  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="glass-panel p-10 sm:p-12 text-center max-w-md w-full">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-surface-800 to-surface-900 border border-surface-700/50 flex items-center justify-center">
          <LayersIcon size={26} className="text-surface-500" />
        </div>
        <h1 className="text-xl font-bold text-surface-100">{title}</h1>
        <p className="text-sm text-surface-400 mt-1 mb-6">
          {description || 'Pick a workspace to get started.'}
        </p>
        <div className="flex justify-center">
          <WorkspaceSelector />
        </div>
      </div>
    </div>
  )
}