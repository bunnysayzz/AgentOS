import { beforeEach, describe, expect, it, vi } from 'vitest'

// The interceptor handlers are exported from api.ts so they can be unit
// tested directly with plain config/error objects — no axios mocking or
// module-graph tricks required. The `api` instance is the axios instance
// created in api.ts (stubbed by the central mock in src/test/setup.ts).
import api, { requestInterceptor, responseErrorInterceptor } from './api'
import { useAuthStore } from '@/stores/authStore'
import { getCurrentIdToken } from '@/services/firebase'

// Plain error stand-in — the interceptor only reads `response.status`,
// `config.url` and `config.headers`.
class MockAxiosError extends Error {
  config: any
  response: any
  constructor(message: string, _code?: string, config?: any) {
    super(message)
    this.config = config
  }
}

function make401Error(url: string) {
  const config = { url, headers: {}, _retry: false }
  const err: any = new MockAxiosError('Unauthorized', 'ERR_BAD_REQUEST', config)
  err.response = { status: 401, data: {} }
  err.config = config
  return err
}

describe('api client interceptors', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    })
    vi.clearAllMocks()
  })

  it('attaches the Bearer token when authenticated', () => {
    useAuthStore.getState().setAuth('access-123', 'refresh-123', null)
    const config = requestInterceptor({ headers: {} } as any)
    expect(config.headers.Authorization).toBe('Bearer access-123')
  })

  it('does not attach a token when logged out', () => {
    const config = requestInterceptor({ headers: {} } as any)
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('refreshes the Firebase token on 401 and retries the original request', async () => {
    useAuthStore.getState().setAuth('old-access', 'refresh-123', null)
    ;(getCurrentIdToken as any).mockResolvedValueOnce('new-access')
    ;(api as any).mockResolvedValue({ data: 'retried-ok' })

    const result = await responseErrorInterceptor(make401Error('/workspaces/'))

    expect(result).toEqual({ data: 'retried-ok' })
    expect(useAuthStore.getState().accessToken).toBe('new-access')
    // The Firebase SDK was asked for a fresh ID token
    expect(getCurrentIdToken).toHaveBeenCalledWith(true)
    // The retried request carried the new token
    const retriedConfig = (api as any).mock.calls[0][0]
    expect(retriedConfig.headers.Authorization).toBe('Bearer new-access')
  })

  it('rejects and logs out when the refresh fails', async () => {
    useAuthStore.getState().setAuth('old-access', 'refresh-123', null)
    ;(getCurrentIdToken as any).mockResolvedValueOnce(null)

    // Stub location so jsdom doesn't throw on the navigation in debouncedLogout
    Object.defineProperty(window, 'location', {
      value: { replace: vi.fn(), href: 'http://localhost/' },
      configurable: true,
      writable: true,
    })

    await expect(responseErrorInterceptor(make401Error('/workspaces/'))).rejects.toBeDefined()

    // Debounced logout clears auth state
    await new Promise((r) => setTimeout(r, 150))
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('passes non-401 errors straight through', async () => {
    const err: any = new MockAxiosError('Bad credentials', 'ERR_BAD_REQUEST', {
      url: '/auth/firebase',
      headers: {},
    })
    err.response = { status: 400, data: { detail: 'Invalid token' } }

    await expect(responseErrorInterceptor(err)).rejects.toEqual(err)
  })
})
