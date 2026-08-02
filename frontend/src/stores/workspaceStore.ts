import { create } from 'zustand'

interface WorkspaceState {
  selectedWorkspaceId: string | null
  selectedWorkspaceName: string | null
  setSelectedWorkspace: (id: string, name: string) => void
  clearSelectedWorkspace: () => void
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  selectedWorkspaceId: null,
  selectedWorkspaceName: null,
  setSelectedWorkspace: (id, name) => set({ selectedWorkspaceId: id, selectedWorkspaceName: name }),
  clearSelectedWorkspace: () => set({ selectedWorkspaceId: null, selectedWorkspaceName: null }),
}))
