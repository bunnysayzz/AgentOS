import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ABTesting from './ABTesting'
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
        <ABTesting />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('ABTesting', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({ selectedWorkspaceId: 'ws-1', selectedWorkspaceName: 'Prod' })
    queryClient.clear()
    vi.clearAllMocks()
    ;(api.get as any).mockImplementation((url: string) => {
      if (url.includes('/prompts')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    })
  })

  it('renders the page with an empty tests state', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('A/B Testing')
    expect(await screen.findByText('No A/B tests yet')).toBeInTheDocument()
  })
})
