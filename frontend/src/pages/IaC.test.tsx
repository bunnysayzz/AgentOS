import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import IaC from './IaC'
import { useWorkspaceStore } from '@/stores/workspaceStore'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function renderPage() {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <IaC />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('IaC', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({ selectedWorkspaceId: 'ws-1', selectedWorkspaceName: 'Prod' })
    queryClient.clear()
    vi.clearAllMocks()
    ;(api.get as any).mockImplementation((url: string) => {
      if (url.includes('/iac/export')) {
        return Promise.resolve({
          data: {
            agentos_version: '1.0',
            exported_at: '2026-08-15T00:00:00Z',
            workspace_id: 'ws-1',
            resources: { agents: [], workflows: [], prompts: [], tools: [] },
            summary: { agents: 0, workflows: 0, prompts: 0, tools: 0 },
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
  })

  it('renders the page with export and import panels', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Infrastructure as Code')
    expect(screen.getByText('Export Workspace')).toBeInTheDocument()
    expect(screen.getByText('Import Manifest')).toBeInTheDocument()
  })
})
