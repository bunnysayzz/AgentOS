import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface WorkspaceState {
  selectedWorkspaceId: string | null
  selectedWorkspaceName: string | null
  setSelectedWorkspace: (id: string, name: string) => void
  clearSelectedWorkspace: () => void
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      selectedWorkspaceId: null,
      selectedWorkspaceName: null,
      setSelectedWorkspace: (id, name) => set({ selectedWorkspaceId: id, selectedWorkspaceName: name }),
      clearSelectedWorkspace: () => set({ selectedWorkspaceId: null, selectedWorkspaceName: null }),
    }),
    {
      name: 'agentos-workspace',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        selectedWorkspaceId: state.selectedWorkspaceId,
        selectedWorkspaceName: state.selectedWorkspaceName,
      }),
    },
  ),
)