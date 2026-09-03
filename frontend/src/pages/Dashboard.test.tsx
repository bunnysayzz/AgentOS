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

// Default guest responses: everything empty (single aggregate endpoint)
function mockEmptyBackend() {
  ;(api.get as any).mockImplementation((url: string) => {
    if (url === '/dashboard/stats') {
      return Promise.resolve({
        data: {
          workspaces: [], workspace_count: 0, model_count: 0, call_count: 0,
          total_tokens: 0, total_cost_usd: 0, key_count: 0, configured_providers: 0,
          first_ws: null, workspace: null,
        },
      })
    }
    return Promise.resolve({ data: [] })
  })
}

describe('Dashboard — guest mode', () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: null, refreshToken: null, user: null,
      isAuthenticated: false, justSignedIn: false,
    })
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
  // Fresh login: justSignedIn is true, so the one-time welcome hero shows.
  function mockAuth(overrides: Record<string, unknown> = {}) {
    useAuthStore.setState({
      accessToken: 'tok', refreshToken: '', isAuthenticated: true,
      user: { id: 'u1', email: 'a@b.com', username: 'a', fullName: 'Ada Lovelace' },
      ...overrides,
    })
  }

  beforeEach(() => {
    mockAuth({ justSignedIn: true })
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
      if (url === '/dashboard/stats') {
        return Promise.resolve({
          data: {
            workspaces: [{ id: 'ws-1', name: 'Prod' }], workspace_count: 1,
            model_count: 1, call_count: 0, total_tokens: 0, total_cost_usd: 0,
            key_count: 1, configured_providers: 1, first_ws: 'ws-1',
            workspace: {
              agent_count: 1, workflow_count: 1, prompt_count: 0, tool_count: 0,
              secret_count: 0, artifact_count: 0, telemetry_events: 0, telemetry_errors: 0,
            },
          },
        })
      }
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

  it('skips the welcome hero after a refresh (justSignedIn cleared) and shows data first', async () => {
    // Return visit after refresh: the ephemeral flag did not survive.
    mockAuth({ justSignedIn: false })
    ;(api.get as any).mockImplementation((url: string) => {
      if (url === '/dashboard/stats') {
        return Promise.resolve({
          data: {
            workspaces: [{ id: 'ws-1', name: 'Prod' }], workspace_count: 1,
            model_count: 3, call_count: 42, total_tokens: 12000, total_cost_usd: 0.0042,
            key_count: 2, configured_providers: 2, first_ws: 'ws-1',
            workspace: {
              agent_count: 2, workflow_count: 1, prompt_count: 4, tool_count: 3,
              secret_count: 2, artifact_count: 5, telemetry_events: 120, telemetry_errors: 3,
            },
          },
        })
      }
      return Promise.resolve({ data: [] })
    })

    renderDashboard()

    // No welcome hero — straight to the premium data dashboard.
    expect(screen.queryByText(/Welcome back/i)).not.toBeInTheDocument()
    expect(await screen.findByText('Overview')).toBeInTheDocument()
    expect(await screen.findByText('Resources')).toBeInTheDocument()
    expect(screen.getByText('Platform Metrics')).toBeInTheDocument()

    // Detailed data renders instead of onboarding copy
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('LLM Calls')).toBeInTheDocument()
    expect(screen.getByText('Activity pulse')).toBeInTheDocument()
    expect(screen.queryByText('Getting Started')).not.toBeInTheDocument()
  })
})
