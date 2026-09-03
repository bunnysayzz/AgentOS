import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Memory from './Memory'
import { useWorkspaceStore } from '@/stores/workspaceStore'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

const recentEntries = [
  { id: 'e1', session_id: 'sess-aaaa1111', role: 'user', content: 'First message', memory_type: 'conversation', importance_score: 0.4, created_at: '2026-08-02T10:00:00Z' },
  { id: 'e2', session_id: 'sess-aaaa1111', role: 'assistant', content: 'A reply', memory_type: 'conversation', importance_score: 0.9, created_at: '2026-08-03T10:00:00Z' },
  { id: 'e3', session_id: 'sess-bbbb2222', role: 'user', content: 'Older session', memory_type: 'conversation', importance_score: 0.1, created_at: '2026-08-01T10:00:00Z' },
]

const sessionEntries = [
  { id: 'e1', session_id: 'sess-aaaa1111', role: 'user', content: 'First message', memory_type: 'conversation', importance_score: 0.4, created_at: '2026-08-02T10:00:00Z' },
]

function renderMemory() {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Memory />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('Memory', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({ selectedWorkspaceId: 'ws1', selectedWorkspaceName: 'Core' })
    queryClient.clear()
    vi.clearAllMocks()
  })

  it('lists recent sessions derived from workspace entries', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url.endsWith('/memory')) return Promise.resolve({ data: recentEntries })
      return Promise.resolve({ data: [] })
    })

    renderMemory()

    expect(await screen.findByText(/sess-aaaa11/)).toBeInTheDocument()
    expect(screen.getByText(/sess-bbbb22/)).toBeInTheDocument()
  })

  it('opens a session by clicking its recent chip and shows importance stars', async () => {
    const user = userEvent.setup()
    ;(api.get as any).mockImplementation((url: string) => {
      if (url.endsWith('/memory')) return Promise.resolve({ data: recentEntries })
      if (url.includes('/sessions/')) return Promise.resolve({ data: sessionEntries })
      return Promise.resolve({ data: [] })
    })

    renderMemory()

    await user.click(await screen.findByText(/sess-aaaa11/))

    expect(await screen.findByText('First message')).toBeInTheDocument()
    expect(screen.getByText(/★ 0.4/)).toBeInTheDocument()
    await waitFor(() =>
      expect(api.get).toHaveBeenCalledWith('/workspaces/ws1/memory/sessions/sess-aaaa1111'),
    )
  })
})
