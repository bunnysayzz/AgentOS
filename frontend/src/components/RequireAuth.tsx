import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useHasHydrated } from './ProtectedRoute'

/**
 * Login-only route guard for account/security pages (Settings, API Keys,
 * Secrets, Providers).
 *
 * Unlike ProtectedRoute — which deliberately lets guests browse the product
 * — these pages own user-specific data and must not render without a
 * session. Guests are sent to /login with the intended destination in the
 * `redirect` query param, so signing in lands them back where they started.
 */
export default function RequireAuth() {
  const hydrated = useHasHydrated()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const location = useLocation()

  if (!hydrated) {
    // Session may still be restoring from storage — never redirect on a
    // guess. (ProtectedRoute already shows this spinner, but RequireAuth
    // stays safe on its own too.)
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
    const target = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?redirect=${target}`} replace />
  }

  return <Outlet />
}
