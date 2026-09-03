import { useId } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/utils/cn'

export interface TabItem<T extends string> {
  id: T
  label: string
  icon?: React.FC<{ size?: number; className?: string }>
}

interface TabBarProps<T extends string> {
  tabs: TabItem<T>[]
  active: T
  onChange: (id: T) => void
  className?: string
}

/**
 * The app's single tab treatment — a pill bar where a gradient pill slides
 * between tabs with a spring. Every page (MCP Gateway, Telemetry, Agents,
 * Tools…) renders the same component, so tabs look and feel identical
 * everywhere.
 */
export default function TabBar<T extends string>({ tabs, active, onChange, className }: TabBarProps<T>) {
  // Unique per instance so pills never animate across sibling bars.
  const pillId = useId()

  return (
    <div
      role="tablist"
      className={cn(
        'flex gap-1 p-1 rounded-2xl bg-surface-800/40 border border-surface-700/20 w-fit flex-wrap',
        className,
      )}
    >
      {tabs.map((t) => {
        const isActive = t.id === active
        const Icon = t.icon
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t.id)}
            className={cn(
              'relative px-4 py-2 rounded-xl text-sm font-medium transition-colors duration-150',
              isActive ? 'text-white' : 'text-surface-400 hover:text-surface-200',
            )}
          >
            {isActive && (
              <motion.span
                layoutId={pillId}
                className="absolute inset-0 rounded-xl bg-gradient-to-b from-primary-500/90 to-primary-600/80 shadow-lg shadow-primary-500/25"
                transition={{ type: 'spring', stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-1.5">
              {Icon && <Icon size={14} />}
              {t.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}