import React from 'react'
import { motion } from 'framer-motion'

interface EmptyStateProps {
  icon: React.FC<{ size?: number; className?: string }>
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

/**
 * Consistent industry-style empty state: an icon tile with a soft accent,
 * a title, a one-line description, and an optional action button.
 * Rendered with a gentle entrance so pages never pop.
 */
export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <motion.div
      className={`glass-panel flex flex-col items-center justify-center px-6 py-14 text-center ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="relative mb-4">
        <div className="absolute inset-0 rounded-2xl bg-primary-500/10 blur-xl" aria-hidden />
        <div className="relative w-14 h-14 rounded-2xl bg-surface-800 border border-surface-700/40 flex items-center justify-center">
          <Icon size={24} className="text-surface-500" />
        </div>
      </div>
      <h3 className="text-base font-medium text-surface-200">{title}</h3>
      {description && (
        <p className="text-sm text-surface-500 mt-1.5 max-w-sm leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  )
}
