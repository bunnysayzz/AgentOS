import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'
import { firebaseAuth, firebaseSignOut } from '@/services/firebase'

const API_BASE = import.meta.env.VITE_API_URL
if (!API_BASE) throw new Error('[api] Missing env var: VITE_API_URL')


const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
})

// ─── Auth endpoints that should NEVER trigger the 401 interceptor ────
const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh']

function isAuthEndpoint(url: string | undefined): boolean {
  if (!url) return false
  return AUTH_ENDPOINTS.some((ep) => url.includes(ep))
}

// ─── Token refresh mutex ─────────────────────────────────────────────
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
    localStorage.clear()
    window.location.replace('/login')
  }, 100)
}

// ─── Interceptor handlers (exported for direct unit testing) ─────────

/**
 * Attaches the current access token to every outgoing request.
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
 * Handles 401 responses with token refresh + request queuing.
 * Exported so tests can invoke it with a plain error object.
 */
export async function responseErrorInterceptor(error: AxiosError) {
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

  // Don't intercept auth endpoints — let the caller handle errors directly
  if (isAuthEndpoint(originalRequest?.url)) {
    return Promise.reject(error)
  }

  if (error.response?.status !== 401) {
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

  // Start a refresh
  const currentState = useAuthStore.getState()
  const refreshToken = currentState.refreshToken

  if (!refreshToken) {
    debouncedLogout()
    return Promise.reject(error)
  }

  isRefreshing = true

  try {
    // Refresh via the same api client (in tests this resolves to the stubbed
    // instance, so no bare-module axios mocking is required). This is safe:
    // the refresh URL is in AUTH_ENDPOINTS, so a 401 on the refresh itself
    // short-circuits in the response interceptor (no recursion), and the
    // stale access token attached by the request interceptor is harmless.
    const { data } = await api.post('/auth/refresh', {
      refresh_token: refreshToken,
    })

    const newAccessToken = data.access_token
    // Update store with new tokens
    currentState.setAuth(newAccessToken, data.refresh_token, currentState.user)

    // Retry all queued requests with the new token
    processPendingRequests(newAccessToken)

    // Retry the original request
    if (originalRequest.headers) {
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
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

// ─── Health ──────────────────────────────────────────────
export const healthCheck = () => api.get('/health')

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
