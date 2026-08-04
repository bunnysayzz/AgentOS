import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
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
})
