import { useEffect, useCallback } from 'react'
import { create } from 'zustand'
import { cn } from '@/utils/cn'
import { CheckCircleIcon, XCircleIcon, AlertCircleIcon, InfoIcon, XIcon } from '@/components/Icons'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
}

interface ToastState {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => string
  removeToast: (id: string) => void
  clearToasts: () => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2)
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }))
    return id
  },
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
  clearToasts: () => set({ toasts: [] }),
}))

// Toast triggers for convenience
export const toast = {
  success: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'success', title, message, duration: 4000 }),
  error: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'error', title, message, duration: 6000 }),
  warning: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'warning', title, message, duration: 5000 }),
  info: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'info', title, message, duration: 4000 }),
}

const iconMap: Record<ToastType, React.FC<{ size?: number; className?: string }>> = {
  success: CheckCircleIcon,
  error: XCircleIcon,
  warning: AlertCircleIcon,
  info: InfoIcon,
}

const colorMap: Record<ToastType, string> = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  error: 'border-red-500/30 bg-red-500/10 text-red-400',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  info: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
}

const iconColorMap: Record<ToastType, string> = {
  success: 'text-emerald-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-blue-400',
}

function ToastItem({ toast: t, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
  const Icon = iconMap[t.type]

  useEffect(() => {
    if (t.duration && t.duration > 0) {
      const timer = setTimeout(() => onRemove(t.id), t.duration)
      return () => clearTimeout(timer)
    }
  }, [t.id, t.duration, onRemove])

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-4 py-3 rounded-xl border shadow-xl backdrop-blur-xl',
        'animate-slide-in-right transition-all duration-300',
        colorMap[t.type],
      )}
    >
      <Icon size={18} className={cn('flex-shrink-0 mt-0.5', iconColorMap[t.type])} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">{t.title}</p>
        {t.message && <p className="text-xs mt-0.5 opacity-80">{t.message}</p>}
      </div>
      <button
        onClick={() => onRemove(t.id)}
        className="flex-shrink-0 p-0.5 rounded-md hover:bg-white/10 transition-colors"
      >
        <XIcon size={14} />
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  const removeToast = useToastStore((s) => s.removeToast)
  const onRemove = useCallback((id: string) => removeToast(id), [removeToast])

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem toast={t} onRemove={onRemove} />
        </div>
      ))}
    </div>
  )
}
