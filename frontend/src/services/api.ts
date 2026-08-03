import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'
import { firebaseAuth, firebaseSignOut, getCurrentIdToken } from '@/services/firebase'

const API_BASE = import.meta.env.VITE_API_URL
if (!API_BASE) throw new Error('[api] Missing env var: VITE_API_URL')


const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
})

// ─── Token refresh mutex (Firebase ID token) ──────────────────────────
let isRefreshing = false
let pendingRequests: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

function processPendingRequests(token: string | null, error?: unknown) {
  pendingRequests.forEach(({ resolve, reject }) => {
    if (token) {
      resolve(token)
    } else {
      reject(error)
    }
  })
  pendingRequests = []
}

// ─── Debounced logout to prevent multiple redirects ──────────────────
let logoutTimer: ReturnType<typeof setTimeout> | null = null

function debouncedLogout() {
  if (logoutTimer) return // already scheduled
  logoutTimer = setTimeout(async () => {
    logoutTimer = null
    try { await firebaseSignOut(firebaseAuth) } catch { /* ignore */ }
    const { clearAuth } = useAuthStore.getState()
    clearAuth()
    // Only clear our own persisted auth key — never nuke other app data.
    localStorage.removeItem('agentos-auth')
    window.location.replace('/login')
  }, 100)
}

// ─── Interceptor handlers (exported for direct unit testing) ─────────

/**
 * Attaches the current Firebase ID token to every outgoing request.
 * Exported so tests can invoke it without a live axios instance.
 */
export function requestInterceptor(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const token = useAuthStore.getState().accessToken
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

/**
 * Handles 401 responses by refreshing the Firebase ID token (Firebase SDK
 * auto-rotates it) and retrying queued requests.
 * Exported so tests can invoke it with a plain error object.
 *
 * Guest mode: when there's no active session at all (visitor browsing the
 * app without signing in), 401s are passed through WITHOUT logging out or
 * redirecting — pages simply show empty/guest states.
 */
export async function responseErrorInterceptor(error: AxiosError) {
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

  if (error.response?.status !== 401) {
    return Promise.reject(error)
  }

  // Guest browsing (no session token yet): don't force-logout/redirect, just
  // let the caller handle the 401 (pages render guest/empty states).
  const currentState = useAuthStore.getState()
  if (!currentState.accessToken) {
    return Promise.reject(error)
  }

  // If this request was already retried, give up
  if (originalRequest._retry) {
    debouncedLogout()
    return Promise.reject(error)
  }

  originalRequest._retry = true

  // If a refresh is already in progress, queue this request
  if (isRefreshing) {
    return new Promise<string>((resolve, reject) => {
      pendingRequests.push({ resolve, reject })
    }).then((newToken) => {
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`
      }
      return api(originalRequest)
    })
  }

  isRefreshing = true

  try {
    // Force the Firebase SDK to mint a fresh ID token (it caches internally)
    const newToken = await getCurrentIdToken(true)
    if (!newToken) {
      throw new Error('No active Firebase session')
    }

    currentState.setAuth(newToken, '', currentState.user)

    // Retry all queued requests with the new token
    processPendingRequests(newToken)

    // Retry the original request
    if (originalRequest.headers) {
      originalRequest.headers.Authorization = `Bearer ${newToken}`
    }
    return api(originalRequest)
  } catch (refreshError) {
    // Refresh failed — reject all queued requests and logout
    processPendingRequests(null, refreshError)
    debouncedLogout()
    return Promise.reject(error)
  } finally {
    isRefreshing = false
  }
}

api.interceptors.request.use(requestInterceptor, (error) => Promise.reject(error))
api.interceptors.response.use((response) => response, responseErrorInterceptor)

// ─── API helpers ──────────────────────────────────────────
export const getApi = <T>(url: string, params?: Record<string, unknown>) =>
  api.get<T>(url, { params })

export const postApi = <T>(url: string, data?: unknown) =>
  api.post<T>(url, data)

export const putApi = <T>(url: string, data?: unknown) =>
  api.put<T>(url, data)

export const deleteApi = <T>(url: string) =>
  api.delete<T>(url)

export default api
