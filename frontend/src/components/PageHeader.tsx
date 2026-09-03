import { type ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  icon?: ReactNode
  actions?: ReactNode
  right?: ReactNode
}

/**
 * Standard page header — every content page uses the same title / subtitle /
 * action row so the app feels like one product instead of a patchwork.
 */
export default function PageHeader({ title, subtitle, icon, actions, right }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500/15 to-primary-700/10 border border-primary-500/15 flex items-center justify-center flex-shrink-0">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-surface-100">{title}</h1>
          {subtitle && <p className="text-surface-400 text-sm mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
        {actions}
        {right}
      </div>
    </div>
  )
}