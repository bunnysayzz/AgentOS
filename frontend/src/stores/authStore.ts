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
  /**
   * Ephemeral (never persisted): true right after a fresh sign-in so the
   * dashboard can show a one-time welcome. Cleared on sign-out, on page
   * refresh (persist does not store it), and once the welcome is shown
   * (acknowledgeWelcome).
   */
  justSignedIn: boolean
  setAuth: (access: string, refresh: string, user: AuthUser | null) => void
  clearAuth: () => void
  setUser: (user: AuthUser | null) => void
  acknowledgeWelcome: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      justSignedIn: false,

      setAuth: (access, refresh, user) => {
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          isAuthenticated: true,
          justSignedIn: true,
        })
      },

      clearAuth: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
          justSignedIn: false,
        })
      },

      setUser: (user) => set({ user }),

      acknowledgeWelcome: () => set({ justSignedIn: false }),
    }),
    {
      name: 'agentos-auth',
      storage: createJSONStorage(() => localStorage),

      // justSignedIn is deliberately NOT persisted: a page refresh must
      // clear it so "Welcome back" only ever shows once, right after login.
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
