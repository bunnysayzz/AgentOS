import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import WorkspaceDetail from './WorkspaceDetail'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/workspaces/ws-1']}>
      <Routes>
        <Route
          path="/workspaces/:workspaceId"
          element={
            <QueryClientProvider client={queryClient}>
              <WorkspaceDetail />
            </QueryClientProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

function mockBackend(overrides: { role?: string; members?: any[] } = {}) {
  const { role = 'owner', members = [] } = overrides
  ;(api.get as any).mockImplementation((url: string) => {
    if (url === '/workspaces/ws-1') {
      return Promise.resolve({ data: { id: 'ws-1', name: 'My Workspace', description: null, role } })
    }
    if (url === '/workspaces/ws-1/members') {
      return Promise.resolve({ data: members })
    }
    if (url === '/users/lookup') {
      return Promise.resolve({ data: { id: 'u-friend', email: 'friend@example.com', username: 'friend' } })
    }
    return Promise.resolve({ data: [] })
  })
}

describe('WorkspaceDetail — members', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.clearAllMocks()
    mockBackend({
      members: [
        { user_id: 'u-owner', role: 'owner', username: 'jonoliver', email: 'jonoliver@ubermail.fun', created_at: '2026-01-01T00:00:00Z' },
        { user_id: 'u-2', role: 'member', username: 'ada', email: 'ada@example.com', created_at: '2026-01-01T00:00:00Z' },
      ],
    })
  })

  it('shows the real role chip and locks the owner role', async () => {
    renderDetail()

    // The chip must show "Owner", not the old hardcoded "member".
    // (Scoped to span.chip — the role <option> also reads "Owner".)
    expect(await screen.findByText('Owner', { selector: 'span.chip' })).toBeInTheDocument()

    // Owner's role selector is disabled and shows Owner; member's is editable.
    const selects = screen.getAllByRole('combobox')
    const ownerSelect = selects.find((s) => (s as HTMLSelectElement).value === 'owner') as HTMLSelectElement
    expect(ownerSelect).toBeDisabled()
    const memberSelect = selects.find((s) => (s as HTMLSelectElement).value === 'member') as HTMLSelectElement
    expect(memberSelect).not.toBeDisabled()
  })

  it('adds a member by email: looks up the user then sends a lowercase role', async () => {
    ;(api.post as any).mockResolvedValue({ data: { user_id: 'u-friend', role: 'member' } })

    const user = userEvent.setup()
    renderDetail()

    await user.click(await screen.findByRole('button', { name: /^add$/i }))
    const modal = await screen.findByTestId('add-member-modal')

    await user.type(within(modal).getByPlaceholderText('team@example.com'), 'friend@example.com')
    await user.click(within(modal).getByRole('button', { name: /^add$/i }))

    await waitFor(() => {
      // Resolved the email via lookup, then POSTed with the resolved id and a
      // LOWERCASE role (the uppercase payload used to 422 silently).
      expect(api.get).toHaveBeenCalledWith('/users/lookup', { params: { email: 'friend@example.com' } })
      expect(api.post).toHaveBeenCalledWith('/workspaces/ws-1/members', {
        user_id: 'u-friend',
        role: 'member',
      })
    })
  })

  it('accepts a raw UUID directly without a lookup (even with {braces})', async () => {
    ;(api.post as any).mockResolvedValue({ data: { user_id: 'ed0dffdf-bf32-4655-bf95-7caacb9b6383', role: 'member' } })

    const user = userEvent.setup()
    renderDetail()

    await user.click(await screen.findByRole('button', { name: /^add$/i }))
    const modal = await screen.findByTestId('add-member-modal')

    // user.type would interpret {…} as key syntax — set the value directly.
    fireEvent.change(within(modal).getByPlaceholderText('team@example.com'), {
      target: { value: '{ed0dffdf-bf32-4655-bf95-7caacb9b6383}' },
    })
    await user.click(within(modal).getByRole('button', { name: /^add$/i }))

    await waitFor(() => {
      expect(api.get).not.toHaveBeenCalledWith('/users/lookup', expect.anything())
      expect(api.post).toHaveBeenCalledWith('/workspaces/ws-1/members', {
        user_id: 'ed0dffdf-bf32-4655-bf95-7caacb9b6383',
        role: 'member',
      })
    })
  })

  it('shows a clear error when the email has no account', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/workspaces/ws-1') return Promise.resolve({ data: { id: 'ws-1', name: 'My Workspace', role: 'owner' } })
      if (url === '/workspaces/ws-1/members') return Promise.resolve({ data: [] })
      if (url === '/users/lookup') {
        return Promise.reject({ response: { status: 404, data: { detail: 'No account found with that email' } } })
      }
      return Promise.resolve({ data: [] })
    })

    const user = userEvent.setup()
    renderDetail()

    await user.click(await screen.findByRole('button', { name: /^add$/i }))
    const modal = await screen.findByTestId('add-member-modal')

    await user.type(within(modal).getByPlaceholderText('team@example.com'), 'ghost@example.com')
    await user.click(within(modal).getByRole('button', { name: /^add$/i }))

    expect(await within(modal).findByText(/no account found with that email/i)).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })
})
