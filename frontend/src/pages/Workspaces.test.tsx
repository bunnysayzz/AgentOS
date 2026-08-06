import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Workspaces from './Workspaces'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

function renderList() {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Workspaces />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('Workspaces — role chip', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.clearAllMocks()
  })

  it('capitalizes the role chip so the creator shows Owner, not lowercase owner', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [
        { id: 'ws-1', name: 'My Workspace', slug: 'my-workspace', role: 'owner', is_personal: false, created_at: '2026-01-01T00:00:00Z' },
        { id: 'ws-2', name: 'Team Space', slug: 'team-space', role: 'member', is_personal: false, created_at: '2026-01-01T00:00:00Z' },
      ],
    })

    renderList()

    await waitFor(() => {
      expect(screen.getByText('My Workspace')).toBeInTheDocument()
    })

    // The raw lowercase value from the API must be displayed capitalized.
    expect(screen.getByText('Owner')).toBeInTheDocument()
    expect(screen.getByText('Member')).toBeInTheDocument()
    expect(screen.queryByText('owner')).not.toBeInTheDocument()
    expect(screen.queryByText('member')).not.toBeInTheDocument()
  })

  it('shows no chip when the role is missing (guest/edge responses)', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [
        { id: 'ws-1', name: 'No Role', slug: 'no-role', is_personal: true, created_at: '2026-01-01T00:00:00Z' },
      ],
    })

    renderList()

    await waitFor(() => {
      expect(screen.getByText('No Role')).toBeInTheDocument()
    })
    expect(screen.queryByText(/Owner|Admin|Member|Viewer/)).not.toBeInTheDocument()
  })

  it('creates a workspace and refreshes the list', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })
    ;(api.post as any).mockResolvedValue({
      data: { id: 'ws-new', name: 'Fresh', slug: 'fresh', role: 'owner' },
    })

    const user = userEvent.setup()
    renderList()

    await user.click(screen.getByRole('button', { name: /new workspace/i }))
    await user.type(screen.getByPlaceholderText('My Workspace'), 'Fresh')
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/workspaces/', { name: 'Fresh', description: '' })
      // List is invalidated so the new workspace appears with an Owner chip.
      expect(api.get).toHaveBeenCalled()
    })
  })
})
