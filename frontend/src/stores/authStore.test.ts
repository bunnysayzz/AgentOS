import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from './authStore'

const USER = { id: 'u1', email: 'a@b.com', username: 'ab', fullName: 'A B' }

describe('authStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    })
  })

  it('starts unauthenticated', () => {
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('setAuth stores tokens and user', () => {
    useAuthStore.getState().setAuth('access', 'refresh', USER)
    const s = useAuthStore.getState()
    expect(s.accessToken).toBe('access')
    expect(s.refreshToken).toBe('refresh')
    expect(s.user).toEqual(USER)
    expect(s.isAuthenticated).toBe(true)
  })

  it('persists to localStorage', () => {
    useAuthStore.getState().setAuth('access', 'refresh', USER)
    const raw = localStorage.getItem('agentos-auth')
    expect(raw).toBeTruthy()
    expect(JSON.parse(raw!).state.accessToken).toBe('access')
  })

  it('clearAuth resets everything', () => {
    useAuthStore.getState().setAuth('a', 'r', USER)
    useAuthStore.getState().clearAuth()
    const s = useAuthStore.getState()
    expect(s.isAuthenticated).toBe(false)
    expect(s.accessToken).toBeNull()
    expect(s.refreshToken).toBeNull()
    expect(s.user).toBeNull()
  })

  it('setUser updates the user without touching tokens', () => {
    useAuthStore.getState().setAuth('a', 'r', USER)
    useAuthStore.getState().setUser({ ...USER, fullName: 'New Name' })
    expect(useAuthStore.getState().user?.fullName).toBe('New Name')
    expect(useAuthStore.getState().accessToken).toBe('a')
  })
})
