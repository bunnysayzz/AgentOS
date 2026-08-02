import { useEffect, useState, useCallback } from 'react'
import { create } from 'zustand'
import { cn } from '@/utils/cn'
import { AlertTriangleIcon, XIcon } from '@/components/Icons'

interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'info'
  onConfirm: () => void | Promise<void>
}

interface ConfirmState {
  options: ConfirmOptions | null
  isOpen: boolean
  loading: boolean
  show: (options: ConfirmOptions) => void
  close: () => void
}

export const useConfirmStore = create<ConfirmState>((set) => ({
  options: null,
  isOpen: false,
  loading: false,
  show: (options) => set({ options, isOpen: true, loading: false }),
  close: () => set({ isOpen: false, options: null, loading: false }),
}))

// Convenience helper
export const confirm = {
  danger: (title: string, message: string, onConfirm: () => void | Promise<void>) =>
    useConfirmStore.getState().show({ title, message, variant: 'danger', onConfirm }),
  warning: (title: string, message: string, onConfirm: () => void | Promise<void>) =>
    useConfirmStore.getState().show({ title, message, variant: 'warning', onConfirm }),
  info: (title: string, message: string, onConfirm: () => void | Promise<void>) =>
    useConfirmStore.getState().show({ title, message, variant: 'info', onConfirm }),
}

const variantStyles = {
  danger: {
    icon: 'text-red-400',
    border: 'border-red-500/30',
    button: 'bg-red-600 hover:bg-red-500 text-white',
  },
  warning: {
    icon: 'text-amber-400',
    border: 'border-amber-500/30',
    button: 'bg-amber-600 hover:bg-amber-500 text-white',
  },
  info: {
    icon: 'text-blue-400',
    border: 'border-blue-500/30',
    button: 'bg-primary-600 hover:bg-primary-500 text-white',
  },
}

export default function ConfirmDialog() {
  const { options, isOpen, loading, close } = useConfirmStore()
  const [animating, setAnimating] = useState(false)

  useEffect(() => {
    if (isOpen) {
      // Small delay to trigger enter animation
      requestAnimationFrame(() => setAnimating(true))
    } else {
      setAnimating(false)
    }
  }, [isOpen])

  const handleConfirm = useCallback(async () => {
    if (!options) return
    useConfirmStore.setState({ loading: true })
    try {
      await options.onConfirm()
    } finally {
      close()
    }
  }, [options, close])

  if (!options) return null

  const styles = variantStyles[options.variant || 'danger']

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          'fixed inset-0 z-50 bg-black/60 transition-opacity duration-200',
          animating ? 'opacity-100' : 'opacity-0',
        )}
        onClick={close}
      />

      {/* Dialog */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className={cn(
            'w-full max-w-md glass-panel p-6 transition-all duration-200',
            animating ? 'scale-100 opacity-100' : 'scale-95 opacity-0',
          )}
        >
          <div className="flex items-start gap-4">
            <div
              className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0',
                'bg-surface-800 border',
                styles.border,
              )}
            >
              <AlertTriangleIcon size={20} className={styles.icon} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-semibold text-surface-100">{options.title}</h3>
              <p className="mt-1 text-sm text-surface-400">{options.message}</p>
            </div>
            <button
              onClick={close}
              className="flex-shrink-0 p-1 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-colors"
            >
              <XIcon size={16} />
            </button>
          </div>

          <div className="flex items-center gap-3 mt-6 justify-end">
            <button
              onClick={close}
              disabled={loading}
              className="btn-secondary"
            >
              {options.cancelText || 'Cancel'}
            </button>
            <button
              onClick={handleConfirm}
              disabled={loading}
              className={cn('px-4 py-2 rounded-xl font-medium text-sm transition-all duration-200', styles.button)}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Processing...
                </span>
              ) : (
                options.confirmText || 'Confirm'
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
