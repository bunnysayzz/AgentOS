import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import WorkspaceSelector from './WorkspaceSelector'
import { useWorkspaceStore } from '@/stores/workspaceStore'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function renderSelector() {
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkspaceSelector />
    </QueryClientProvider>,
  )
}

describe('WorkspaceSelector', () => {
  beforeEach(() => {
    useWorkspaceStore.getState().clearSelectedWorkspace()
    vi.clearAllMocks()
  })

  it('renders nothing when there are no workspaces', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })
    renderSelector()
    await screen.findByText('Select workspace').catch(() => {})
    expect(screen.queryByRole('button', { name: /select workspace/i })).not.toBeInTheDocument()
  })

  it('opens the dropdown and selects a workspace', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [
        { id: 'ws-1', name: 'Alpha' },
        { id: 'ws-2', name: 'Beta' },
      ],
    })
    const user = userEvent.setup()
    renderSelector()

    await user.click(await screen.findByRole('button', { name: /select workspace/i }))
    await user.click(await screen.findByText('Alpha'))

    expect(useWorkspaceStore.getState().selectedWorkspaceId).toBe('ws-1')
    expect(useWorkspaceStore.getState().selectedWorkspaceName).toBe('Alpha')
  })

  it('shows the selected workspace name on the button', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [{ id: 'ws-1', name: 'Alpha' }],
    })
    useWorkspaceStore.getState().setSelectedWorkspace('ws-1', 'Alpha')
    const user = userEvent.setup()
    renderSelector()

    // Button now shows the selected workspace name
    const button = await screen.findByRole('button', { name: /alpha/i })
    expect(button).toBeInTheDocument()
    await user.click(button)
    // Dropdown opens and also lists the workspace option
    expect(await screen.findAllByText('Alpha')).toHaveLength(2)
  })
})
