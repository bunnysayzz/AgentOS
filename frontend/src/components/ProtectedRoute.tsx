import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

/**
 * Use zustand persist's built-in hydration tracking via useSyncExternalStore
 * for a race-condition-free approach.
 */
function useHasHydrated() {
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    // Check if already hydrated (covers synchronous localStorage hydration)
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true)
      return
    }

    // Otherwise wait for async hydration to complete
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      setHydrated(true)
    })

    return unsub
  }, [])

  return hydrated
}

export default function ProtectedRoute() {
  const hydrated = useHasHydrated()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  if (!hydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-surface-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
