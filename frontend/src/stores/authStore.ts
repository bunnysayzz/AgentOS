import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface AuthUser {
  id: string
  email: string
  username: string
  fullName: string
  avatarUrl?: string
  isSuperuser?: boolean
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  setAuth: (access: string, refresh: string, user: AuthUser | null) => void
  clearAuth: () => void
  setUser: (user: AuthUser | null) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      setAuth: (access, refresh, user) => {
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          isAuthenticated: true,
        })
      },

      clearAuth: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        })
      },

      setUser: (user) => set({ user }),
    }),
    {
      name: 'agentos-auth',
      storage: createJSONStorage(() => localStorage),

      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),

      merge: (persisted, current) => {
        const persistedState = persisted as Partial<AuthState> | undefined
        if (!persistedState) return current

        if (current.isAuthenticated && current.accessToken) {
          return current
        }

        return {
          ...current,
          accessToken: persistedState.accessToken ?? current.accessToken,
          refreshToken: persistedState.refreshToken ?? current.refreshToken,
          user: persistedState.user ?? current.user,
          isAuthenticated: persistedState.isAuthenticated ?? current.isAuthenticated,
        }
      },
    },
  ),
)
