import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
// axios and firebase are mocked centrally in src/test/setup.ts
import Login from './Login'
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'
import { loginWithFirebaseEmail, loginWithGoogle } from '@/services/firebase'

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  )
}

describe('Login', () => {
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

  it('renders the sign-in form', async () => {
    renderLogin()
    expect(await screen.findByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in$/i })).toBeInTheDocument()
  })

  it('logs in with Firebase email and stores the profile', async () => {
    ;(loginWithFirebaseEmail as any).mockResolvedValueOnce({
      user: { email: 'a@b.com', displayName: 'A B', photoURL: 'https://x/p.png' },
      idToken: 'firebase-id-token',
    })
    ;(axios.get as any).mockResolvedValueOnce({
      data: { id: 'u1', email: 'a@b.com', username: 'ab', full_name: 'A B', avatar_url: null, is_superuser: false },
    })

    const user = userEvent.setup()
    renderLogin()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in$/i }))

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true))
    expect(useAuthStore.getState().accessToken).toBe('firebase-id-token')
    expect(useAuthStore.getState().user?.email).toBe('a@b.com')
    expect(loginWithFirebaseEmail).toHaveBeenCalledWith('a@b.com', 'password123')
    expect(axios.get).toHaveBeenCalledWith(
      `${import.meta.env.VITE_API_URL}/auth/me`,
      expect.objectContaining({ headers: { Authorization: 'Bearer firebase-id-token' } }),
    )
  })

  it('shows a friendly error on invalid credentials', async () => {
    ;(loginWithFirebaseEmail as any).mockRejectedValueOnce({
      code: 'auth/invalid-credential',
      message: 'Firebase: The supplied auth credential is incorrect.',
    })

    const user = userEvent.setup()
    renderLogin()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in$/i }))

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('toggles password visibility', async () => {
    const user = userEvent.setup()
    renderLogin()
    const password = await screen.findByPlaceholderText('••••••••')
    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: /show password/i }))
    expect(password).toHaveAttribute('type', 'text')
  })

  it('treats the benign hidden-tab storage error like a cancelled popup', async () => {
    // The Firebase SDK throws "Database is closing/hidden" (no error code)
    // when a background IndexedDB write races with the tab being hidden —
    // e.g. a sign-in popup stealing focus on desktop. It must never surface
    // as a scary error banner; the form simply shows again.
    ;(loginWithGoogle as any).mockRejectedValueOnce(new Error('Database is closing/hidden'))

    const user = userEvent.setup()
    renderLogin()

    await user.click(await screen.findByRole('button', { name: /sign in with google/i }))

    // Form comes back, no error banner, still not authenticated.
    expect(await screen.findByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(screen.queryByTestId('auth-error')).not.toBeInTheDocument()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('shows an error banner for real Google sign-in failures', async () => {
    ;(loginWithGoogle as any).mockRejectedValueOnce({
      code: 'auth/network-request-failed',
      message: 'A network error (such as timeout, interrupted connection) has occurred.',
    })

    const user = userEvent.setup()
    renderLogin()

    await user.click(await screen.findByRole('button', { name: /sign in with google/i }))

    expect(await screen.findByTestId('auth-error')).toHaveTextContent(/network error/i)
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('shows a friendly message instead of the raw SDK text for auth/internal-error', async () => {
    // Safari fullscreen can surface the SDK's generic popup-plumbing error.
    // The raw "Firebase: Error (auth/internal-error)." text must never be
    // shown to users — a clear, actionable message takes its place.
    ;(loginWithGoogle as any).mockRejectedValueOnce({
      code: 'auth/internal-error',
      message: 'Firebase: Error (auth/internal-error).',
    })

    const user = userEvent.setup()
    renderLogin()

    await user.click(await screen.findByRole('button', { name: /sign in with google/i }))

    expect(await screen.findByTestId('auth-error')).toHaveTextContent(/temporary browser issue/i)
    expect(screen.queryByText(/auth\/internal-error/)).not.toBeInTheDocument()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('returns to the page the guest was headed to after sign-in', async () => {
    ;(loginWithFirebaseEmail as any).mockResolvedValueOnce({
      user: { email: 'a@b.com', displayName: 'A B', photoURL: null, emailVerified: true },
      idToken: 'firebase-id-token',
    })

    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/login?redirect=/profile']}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/profile" element={<div>profile-marker</div>} />
          <Route path="/dashboard" element={<div>dashboard-marker</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in$/i }))

    // Back to Settings — not the generic dashboard.
    expect(await screen.findByText('profile-marker')).toBeInTheDocument()
  })

  it('sends unverified users to the verification screen even with a redirect target', async () => {
    ;(loginWithFirebaseEmail as any).mockResolvedValueOnce({
      user: { email: 'a@b.com', displayName: 'A B', photoURL: null, emailVerified: false },
      idToken: 'firebase-id-token',
    })

    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/login?redirect=/profile']}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/verify-email" element={<div>verify-marker</div>} />
          <Route path="/dashboard" element={<div>dashboard-marker</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in$/i }))

    expect(await screen.findByText('verify-marker')).toBeInTheDocument()
    expect(screen.queryByText('profile-marker')).not.toBeInTheDocument()
  })

  it('restores the form instead of hanging when the redirect flow silently fails to navigate', async () => {
    // loginWithGoogle resolves null = the same-tab redirect was initiated.
    // If the browser silently swallows the navigation (Safari ITP, popup
    // blockers, in-app browsers), the user must not be stuck on the
    // "Signing you in…" spinner forever: the safety net restores the form
    // and explains what happened.
    vi.useFakeTimers()
    try {
      ;(loginWithGoogle as any).mockResolvedValueOnce(null)
      renderLogin()

      fireEvent.click(screen.getByRole('button', { name: /sign in with google/i }))
      // Let loginWithGoogle resolve (sets the 6s navigation-safety timer)…
      await vi.advanceTimersByTimeAsync(0)
      // …then fire it: form restored + friendly message, no infinite spinner.
      await vi.advanceTimersByTimeAsync(6000)

      expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument()
      expect(screen.getByTestId('auth-error')).toHaveTextContent(/didn.t complete/i)
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })
})
