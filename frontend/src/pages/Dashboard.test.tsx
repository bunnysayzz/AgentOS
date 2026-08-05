import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './Dashboard'
import { useAuthStore } from '@/stores/authStore'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function renderDashboard() {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Dashboard />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

// Default guest responses: everything empty
function mockEmptyBackend() {
  ;(api.get as any).mockImplementation((url: string) => {
    if (url === '/mcp/models') return Promise.resolve({ data: [] })
    if (url === '/mcp/calls') return Promise.resolve({ data: [] })
    if (url === '/api-keys/') return Promise.resolve({ data: [] })
    if (url === '/mcp/providers') return Promise.resolve({ data: [] })
    // workspaces (default)
    return Promise.resolve({ data: [] })
  })
}

describe('Dashboard — guest mode', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false })
    queryClient.clear()
    vi.clearAllMocks()
    mockEmptyBackend()
  })

  it('shows a single clear sign-in CTA with the getting-started checklist', async () => {
    renderDashboard()

    // Hero headline (split across a gradient span, so match on textContent)
    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading.textContent).toMatch(/Build agents that work while you sleep/i)

    // One clear sign-in CTA
    expect(screen.getByRole('link', { name: /sign in to save your work/i })).toBeInTheDocument()

    // Getting-started checklist guides the new user
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('Create a workspace')).toBeInTheDocument()
    expect(screen.getByText('Connect an AI provider')).toBeInTheDocument()
    expect(screen.getByText('Build your first agent')).toBeInTheDocument()
    expect(screen.getByText('Run your first workflow')).toBeInTheDocument()

    // Zero-stats are hidden — they'd read as broken for a guest
    expect(screen.queryByText('Platform Metrics')).not.toBeInTheDocument()
    expect(screen.queryByText('Resources')).not.toBeInTheDocument()

    // Feature discovery remains
    expect(screen.getByText('Explore the platform')).toBeInTheDocument()
    expect(screen.getByText('MCP Gateway')).toBeInTheDocument()
  })

  it('links the checklist steps to the right pages', async () => {
    renderDashboard()
    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading.textContent).toMatch(/Build agents that work while you sleep/i)

    expect(screen.getByRole('link', { name: /create a workspace/i })).toHaveAttribute('href', '/workspaces')
    expect(screen.getByRole('link', { name: /connect an ai provider/i })).toHaveAttribute('href', '/providers')
    expect(screen.getByRole('link', { name: /build your first agent/i })).toHaveAttribute('href', '/agents')
    expect(screen.getByRole('link', { name: /run your first workflow/i })).toHaveAttribute('href', '/workflows')
  })
})

describe('Dashboard — authenticated', () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: 'tok', refreshToken: '', isAuthenticated: true,
      user: { id: 'u1', email: 'a@b.com', username: 'a', fullName: 'Ada Lovelace' },
    })
    queryClient.clear()
    vi.clearAllMocks()
    mockEmptyBackend()
  })

  it('shows the getting-started checklist, not broken zero-stats, when the user has no workspace yet', async () => {
    renderDashboard()

    expect(await screen.findByText(/Welcome back, Ada/i)).toBeInTheDocument()

    // New user with no data gets guided, not shown a wall of zeros
    expect(await screen.findByText('Getting Started')).toBeInTheDocument()
    expect(screen.queryByText('Resources')).not.toBeInTheDocument()
    expect(screen.queryByText('Platform Metrics')).not.toBeInTheDocument()
  })

  it('welcomes the user and shows real stats when a workspace exists', async () => {
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/mcp/models') return Promise.resolve({ data: [{ id: 'm1' }] })
      if (url === '/mcp/calls') return Promise.resolve({ data: [] })
      if (url === '/api-keys/') return Promise.resolve({ data: [{ id: 'k1' }] })
      if (url === '/mcp/providers') return Promise.resolve({ data: [{ id: 'p1', is_configured: true }] })
      if (url === '/workspaces/') return Promise.resolve({ data: [{ id: 'ws-1', name: 'Prod' }] })
      if (url.startsWith('/workspaces/ws-1')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    })

    renderDashboard()

    expect(await screen.findByText(/Welcome back, Ada/i)).toBeInTheDocument()
    expect(await screen.findByText('Resources')).toBeInTheDocument()
    expect(screen.getByText('Platform Metrics')).toBeInTheDocument()

    // Single workspace renders a stat card, not the multi-workspace selector
    expect(screen.queryByText('Prod')).not.toBeInTheDocument()
    expect(screen.getByText('Workspaces').closest('a')).toHaveAttribute('href', '/workspaces')

    // Once stats resolve with a workspace, the checklist and guest CTA disappear
    await waitFor(() => {
      expect(screen.queryByText('Getting Started')).not.toBeInTheDocument()
    })
    expect(screen.queryByText('Sign in to save your work')).not.toBeInTheDocument()
  })
})
