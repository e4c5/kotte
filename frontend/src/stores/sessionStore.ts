/**
 * Session state management.
 */

import { create } from 'zustand'
import { sessionAPI, type ConnectionConfig, type SessionStatus } from '../services/session'

interface SessionState {
  status: SessionStatus | null
  loading: boolean
  error: string | null

  // Actions
  connect: (config: ConnectionConfig) => Promise<void>
  disconnect: () => Promise<void>
  refreshStatus: () => Promise<void>
  clearError: () => void
}

export const useSessionStore = create<SessionState>((set, get) => ({
  status: null,
  loading: false,
  error: null,

  connect: async (config: ConnectionConfig) => {
    set({ loading: true, error: null })
    try {
      await sessionAPI.connect(config)
      await get().refreshStatus()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Connection failed'
      set({ error: message, loading: false })
      throw error
    } finally {
      set({ loading: false })
    }
  },

  disconnect: async () => {
    set({ loading: true })
    try {
      await sessionAPI.disconnect()
      set({ status: null })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Disconnect failed'
      set({ error: message })
    } finally {
      set({ loading: false })
    }
  },

  refreshStatus: async () => {
    try {
      const status = await sessionAPI.getStatus()
      set({ status, error: null })
    } catch (error) {
      // If status check fails, we're likely not connected
      set({ status: null })
    }
  },

  clearError: () => set({ error: null }),
}))

