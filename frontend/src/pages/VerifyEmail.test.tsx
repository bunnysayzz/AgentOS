import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import VerifyEmail from './VerifyEmail'
import { useAuthStore } from '@/stores/authStore'

// File-level mock of '@/services/firebase' (overrides the central stub in
// src/test/setup.ts) so we control the current user + service functions.
const firebaseMocks = vi.hoisted(() => ({
  firebaseAuth: { currentUser: null as any },
  resendVerificationEmail: vi.fn().mockResolvedValue(undefined),
  reloadFirebaseUser: vi.fn(),
}))

vi.mock('@/services/firebase', () => firebaseMocks)

function setUser(overrides: Partial<{ email: string; emailVerified: boolean }> = {}) {
  firebaseMocks.firebaseAuth.currentUser = {
    email: 'a@b.com',
    emailVerified: false,
    ...overrides,
  }
}

function renderVerify() {
  return render(
    <MemoryRouter initialEntries={['/verify-email']}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/dashboard" element={<div>dashboard-marker</div>} />
        <Route path="/login" element={<div>login-marker</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('VerifyEmail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    firebaseMocks.resendVerificationEmail.mockResolvedValue(undefined)
    firebaseMocks.reloadFirebaseUser.mockResolvedValue({ email: 'a@b.com', emailVerified: false })
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    })
    vi.useRealTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the verification card with the email and a resend button', async () => {
    setUser({ emailVerified: false })
    renderVerify()

    expect(await screen.findByRole('heading', { name: /verify your email/i })).toBeInTheDocument()
    expect(screen.getByText('a@b.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /resend verification email/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /continue to dashboard/i })).toBeInTheDocument()
  })

  it('resends the verification email and confirms', async () => {
    setUser({ emailVerified: false })
    const user = userEvent.setup()
    renderVerify()

    await user.click(await screen.findByRole('button', { name: /resend verification email/i }))

    expect(firebaseMocks.resendVerificationEmail).toHaveBeenCalledTimes(1)
    expect(await screen.findByTestId('resend-confirmation')).toBeInTheDocument()
  })

  it('shows a friendly message when resend hits a rate limit', async () => {
    setUser({ emailVerified: false })
    firebaseMocks.resendVerificationEmail.mockRejectedValue({ code: 'auth/too-many-requests' })
    const user = userEvent.setup()
    renderVerify()

    await user.click(await screen.findByRole('button', { name: /resend verification email/i }))

    expect(await screen.findByText(/too many requests/i)).toBeInTheDocument()
  })

  it('polls Firebase, detects the click on the link, and lands on the dashboard', async () => {
    setUser({ emailVerified: false })
    // Next reload reports the account as verified (the user clicked the link).
    firebaseMocks.reloadFirebaseUser.mockResolvedValue({ email: 'a@b.com', emailVerified: true })
    vi.useFakeTimers()
    renderVerify()

    // Fire the 3s poll (sync advance + microtask flush inside act).
    await act(async () => {
      vi.advanceTimersByTime(3000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(screen.getByRole('heading', { name: /email verified!/i })).toBeInTheDocument()

    // Let the 1.4s success pause elapse → auto-navigate to the dashboard.
    await act(async () => {
      vi.advanceTimersByTime(1400)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(screen.getByText('dashboard-marker')).toBeInTheDocument()
  })

  it('goes straight to the dashboard when the email is already verified', async () => {
    setUser({ emailVerified: true })
    renderVerify()

    expect(await screen.findByText('dashboard-marker')).toBeInTheDocument()
  })

  it('redirects to login when there is no Firebase session', async () => {
    firebaseMocks.firebaseAuth.currentUser = null
    renderVerify()

    expect(await screen.findByText('login-marker')).toBeInTheDocument()
  })

  it('waits for a restoring session instead of bouncing to login', async () => {
    // Direct page load: the persisted session restores asynchronously, so
    // currentUser is null at mount. The page must NOT redirect before the
    // grace window elapses.
    firebaseMocks.firebaseAuth.currentUser = null
    vi.useFakeTimers()
    renderVerify()

    expect(screen.queryByText('login-marker')).not.toBeInTheDocument()

    // Session restores during the grace window → go to the dashboard, not login.
    setUser({ emailVerified: true })
    await act(async () => {
      vi.advanceTimersByTime(700)
      await Promise.resolve()
    })

    expect(screen.getByText('dashboard-marker')).toBeInTheDocument()
  })

  it('redirects to the dashboard when there is a backend session but no Firebase user', async () => {
    firebaseMocks.firebaseAuth.currentUser = null
    useAuthStore.setState({
      accessToken: 'tok',
      refreshToken: '',
      user: { id: 'u1', email: 'a@b.com', username: 'a', fullName: 'A' },
      isAuthenticated: true,
    })
    renderVerify()

    expect(await screen.findByText('dashboard-marker')).toBeInTheDocument()
  })
})
