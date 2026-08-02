import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
// axios and firebase are mocked centrally in src/test/setup.ts
import Login from './Login'
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

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

  it('logs in with email and stores the tokens', async () => {
    ;(axios.post as any).mockResolvedValueOnce({
      data: { access_token: 'access-token', refresh_token: 'refresh-token' },
    })
    ;(axios.get as any).mockResolvedValueOnce({
      data: { id: 'u1', email: 'a@b.com', username: 'ab', full_name: 'A B', is_superuser: false },
    })

    const user = userEvent.setup()
    renderLogin()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in$/i }))

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true))
    expect(useAuthStore.getState().accessToken).toBe('access-token')
    expect(useAuthStore.getState().refreshToken).toBe('refresh-token')
    expect(useAuthStore.getState().user?.email).toBe('a@b.com')
    expect(axios.post).toHaveBeenCalledWith(
      `${import.meta.env.VITE_API_URL}/auth/login`,
      { email: 'a@b.com', password: 'password123' },
    )
  })

  it('shows the API error message on invalid credentials', async () => {
    ;(axios.post as any).mockRejectedValueOnce({
      response: { data: { detail: 'Invalid email or password' } },
    })

    const user = userEvent.setup()
    renderLogin()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in$/i }))

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument()
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
})
