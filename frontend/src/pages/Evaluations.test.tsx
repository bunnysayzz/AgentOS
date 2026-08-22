import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Evaluations from './Evaluations'
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
        <Evaluations />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('Evaluations', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({ selectedWorkspaceId: 'ws-1', selectedWorkspaceName: 'Prod' })
    queryClient.clear()
    vi.clearAllMocks()
    ;(api.get as any).mockImplementation((url: string) => {
      if (url.includes('/agents/')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    })
  })

  it('renders the page with an empty suites state', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Evaluations')
    expect(await screen.findByText('No evaluation suites yet')).toBeInTheDocument()
  })

  it('auto-runs a selected run via the execute endpoint', async () => {
    const suite = {
      id: 'suite-1', name: 'Quality', description: null,
      test_cases: [{ id: 'tc-1', input: 'hi', expected_output: 'hello', criteria: null, tags: [], created_at: '2026-01-01' }],
      created_at: '2026-01-01', updated_at: '2026-01-01',
    }
    const run: any = {
      id: 'run-1', suite_id: 'suite-1', agent_id: null, model_name: 'gpt-4o',
      status: 'pending', results: [], summary: null,
      created_at: '2026-01-01', completed_at: null,
    }
    const executed: any = {
      ...run, status: 'completed',
      summary: { total: 1, passed: 1, failed: 0, pass_rate: 100, avg_score: 0.9, min_score: 0.9, max_score: 0.9 },
      results: [{ id: 'r1', test_case_id: 'tc-1', input: 'hi', actual_output: 'hello', score: 0.9, judge_reasoning: 'ok', passed: true, created_at: '2026-01-01' }],
    }
    let currentRun = run
    ;(api.get as any).mockImplementation((url: string) => {
      if (url.includes('/agents/')) return Promise.resolve({ data: [] })
      if (url.includes('/evaluations/suites')) return Promise.resolve({ data: [suite] })
      if (url.includes('/evaluations/runs')) return Promise.resolve({ data: [currentRun] })
      return Promise.resolve({ data: [] })
    })
    ;(api.post as any).mockImplementation((url: string) => {
      if (url.endsWith('/execute')) {
        currentRun = executed
        return Promise.resolve({ data: executed })
      }
      return Promise.resolve({ data: run })
    })

    renderPage()
    fireEvent.click(await screen.findByText('Quality'))
    fireEvent.click(await screen.findByText('run-1'))
    fireEvent.click(screen.getByRole('button', { name: /auto-run/i }))

    expect((await screen.findAllByText('100%')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('0.9')).length).toBeGreaterThan(0)
    expect(api.post).toHaveBeenCalledWith('/workspaces/ws-1/evaluations/runs/run-1/execute')
  })
})
