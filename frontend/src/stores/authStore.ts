/**
 * Authentication store.
 */

import { create } from 'zustand'
import { authAPI, type UserInfo } from '../services/auth'

interface AuthState {
  user: UserInfo | null
  authenticated: boolean
  loading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  authenticated: false,
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null })
    try {
      const response = await authAPI.login({ username, password })
      set({
        user: { user_id: response.user_id, username: response.username },
        authenticated: true,
        loading: false,
      })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Login failed'
      set({ error: message, loading: false, authenticated: false })
      throw error
    }
  },

  logout: async () => {
    set({ loading: true })
    try {
      await authAPI.logout()
      set({
        user: null,
        authenticated: false,
        loading: false,
      })
    } catch (error) {
      // Even if logout fails, clear local state
      set({
        user: null,
        authenticated: false,
        loading: false,
      })
    }
  },

  checkAuth: async () => {
    set({ loading: true })
    try {
      const user = await authAPI.getCurrentUser()
      set({
        user,
        authenticated: true,
        loading: false,
      })
    } catch (error) {
      set({
        user: null,
        authenticated: false,
        loading: false,
      })
    }
  },

  clearError: () => set({ error: null }),
}))

