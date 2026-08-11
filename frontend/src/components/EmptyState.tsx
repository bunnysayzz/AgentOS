import { motion } from 'framer-motion'
import { type ReactNode } from 'react'


interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <motion.div
      className={`glass-panel p-12 text-center ${className || ''}`}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <motion.div
        className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-surface-800 to-surface-900 border border-surface-700/50 flex items-center justify-center"
        animate={{ y: [0, -5, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="text-surface-500">{icon}</div>
      </motion.div>
      <h3 className="text-lg font-medium text-surface-300 mb-2">{title}</h3>
      <p className="text-sm text-surface-500 max-w-sm mx-auto mb-6">{description}</p>
      {action}
    </motion.div>
  )
}

export default EmptyState
