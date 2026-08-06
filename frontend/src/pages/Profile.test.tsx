import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Profile from './Profile'
import ConfirmDialog from '@/components/ConfirmDialog'
import ToastContainer from '@/components/Toast'
import { useAuthStore } from '@/stores/authStore'
import { firebaseSignOut, firebaseAuth, deleteAvatar } from '@/services/firebase'
import api from '@/services/api'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

function renderProfile() {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Profile />
        <ConfirmDialog />
        <ToastContainer />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function mockProfile() {
  ;(api.get as any).mockResolvedValue({
    data: {
      id: 'u1',
      email: 'a@b.com',
      username: 'ab',
      full_name: 'Ada B',
      avatar_url: null,
      is_active: true,
      is_superuser: false,
      is_verified: true,
      last_login_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
    },
  })
}

describe('Profile — Danger Zone', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({
      accessToken: 'tok',
      refreshToken: '',
      isAuthenticated: true,
      user: { id: 'u1', email: 'a@b.com', username: 'ab', fullName: 'Ada B', avatarUrl: undefined },
    })
    queryClient.clear()
    vi.clearAllMocks()
    mockProfile()
  })

  it('renders the Danger Zone with export and delete actions', async () => {
    renderProfile()
    expect(await screen.findByText('Danger Zone')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /export data/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete account/i })).toBeInTheDocument()
  })

  it('downloads the JSON export when Export data is clicked', async () => {
    // jsdom has no URL.createObjectURL — stub it.
    const createSpy = vi.fn(() => 'blob:fake-url')
    const revokeSpy = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL: createSpy, revokeObjectURL: revokeSpy })
    const clickSpy = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(clickSpy)

    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/users/me') {
        return Promise.resolve({
          data: { id: 'u1', email: 'a@b.com', username: 'ab', full_name: 'Ada B', avatar_url: null, is_active: true, is_superuser: false, is_verified: true, last_login_at: null, created_at: '2026-01-01T00:00:00Z', updated_at: null },
        })
      }
      if (url === '/users/me/export') {
        return Promise.resolve({ data: new Blob(['{"user":{}}'], { type: 'application/json' }) })
      }
      return Promise.resolve({ data: [] })
    })

    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: /export data/i }))

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/users/me/export', { responseType: 'blob' })
      expect(clickSpy).toHaveBeenCalled()
    })
  })

  it('deletes the account after confirmation and signs out', async () => {
    ;(api.delete as any).mockResolvedValue({ status: 204 })

    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: /delete account/i }))

    // Confirmation dialog appears.
    expect(await screen.findByText(/Delete your account\?/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /confirm/i }))

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/users/me')
      expect(deleteAvatar).toHaveBeenCalled()
      expect(firebaseSignOut).toHaveBeenCalledWith(firebaseAuth)
    })
  })

  it('surfaces a delete error without signing out', async () => {
    ;(api.delete as any).mockRejectedValue({
      response: { data: { detail: 'Could not delete your account.' } },
    })

    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: /delete account/i }))
    expect(await screen.findByText(/Delete your account\?/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /confirm/i }))

    await waitFor(() => {
      expect(firebaseSignOut).not.toHaveBeenCalled()
    })
    // The failure surfaces as an error toast.
    expect(await screen.findByText(/delete failed/i)).toBeInTheDocument()
    expect(screen.getByText('Could not delete your account.')).toBeInTheDocument()
  })
})
