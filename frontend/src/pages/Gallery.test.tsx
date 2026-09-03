import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Gallery from './Gallery'
import { useAuthStore } from '@/stores/authStore'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

const publishedAgents = [
  {
    id: 'agent-1',
    name: 'PR Summarizer',
    description: 'Drafts pull-request summaries from diffs.',
    system_prompt: 'Summarize the changes in this diff.',
    model_provider: 'openai',
    model_name: 'gpt-4o-mini',
    status: 'active',
    author_username: 'dev',
    workspace_name: 'Core',
    published_at: '2026-08-01T00:00:00Z',
  },
]

function renderGallery(initialEntries = ['/gallery']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/gallery" element={<Gallery />} />
          <Route path="/login" element={<div>login-marker</div>} />
          <Route path="/agents" element={<div>agents-marker</div>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('Gallery', () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    })
    queryClient.clear()
    vi.clearAllMocks()
    ;(api.get as any).mockResolvedValue({ data: publishedAgents })
  })

  it('renders published agents from the public gallery', async () => {
    renderGallery()

    expect(await screen.findByText('PR Summarizer')).toBeInTheDocument()
    expect(screen.getByText(/Drafts pull-request summaries/)).toBeInTheDocument()
    expect(screen.getByText(/@dev/)).toBeInTheDocument()
    expect(screen.getByText('gpt-4o-mini')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/gallery/')
  })

  it('opens the detail modal with the system prompt', async () => {
    const user = userEvent.setup()
    renderGallery()

    await user.click(await screen.findByText('PR Summarizer'))

    expect(screen.getByText('System prompt')).toBeInTheDocument()
    expect(screen.getByText(/Summarize the changes in this diff/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in to clone/i })).toBeInTheDocument()
  })

  it('sends guests to login (and back to the gallery) when they use an agent', async () => {
    const user = userEvent.setup()
    renderGallery()

    await user.click(await screen.findByRole('button', { name: /use this agent/i }))

    expect(await screen.findByText('login-marker')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('clones the agent into the workspace when signed in', async () => {
    useAuthStore.setState({
      accessToken: 't',
      refreshToken: '',
      user: { id: 'u1', email: 'a@b.com', username: 'a', fullName: 'A' },
      isAuthenticated: true,
    })
    ;(api.post as any).mockResolvedValue({
      data: { id: 'clone-1', name: 'PR Summarizer' },
    })

    const user = userEvent.setup()
    renderGallery()

    await user.click(await screen.findByRole('button', { name: /use this agent/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/gallery/agent-1/clone'))
    expect(await screen.findByText('agents-marker')).toBeInTheDocument()
  })

  it('shows an empty state when nothing is published yet', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })

    renderGallery()

    expect(await screen.findByText('No agents published yet')).toBeInTheDocument()
  })
})
