import { describe, expect, it } from 'vitest'
import { useWorkspaceStore } from './workspaceStore'

describe('workspaceStore', () => {
  it('starts with no selection', () => {
    expect(useWorkspaceStore.getState().selectedWorkspaceId).toBeNull()
    expect(useWorkspaceStore.getState().selectedWorkspaceName).toBeNull()
  })

  it('sets and clears the selected workspace', () => {
    useWorkspaceStore.getState().setSelectedWorkspace('ws-1', 'My Workspace')
    expect(useWorkspaceStore.getState().selectedWorkspaceId).toBe('ws-1')
    expect(useWorkspaceStore.getState().selectedWorkspaceName).toBe('My Workspace')

    useWorkspaceStore.getState().clearSelectedWorkspace()
    expect(useWorkspaceStore.getState().selectedWorkspaceId).toBeNull()
    expect(useWorkspaceStore.getState().selectedWorkspaceName).toBeNull()
  })

  it('overwrites a previous selection', () => {
    useWorkspaceStore.getState().setSelectedWorkspace('ws-1', 'A')
    useWorkspaceStore.getState().setSelectedWorkspace('ws-2', 'B')
    expect(useWorkspaceStore.getState().selectedWorkspaceId).toBe('ws-2')
    expect(useWorkspaceStore.getState().selectedWorkspaceName).toBe('B')
  })
})
