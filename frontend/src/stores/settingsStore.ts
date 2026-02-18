/**
 * Application settings with localStorage persistence.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark' | 'auto'
export type ViewMode = 'graph' | 'table'
export type DefaultViewMode = 'graph' | 'table' | 'auto'

export interface AppSettings {
  // Theme
  theme: Theme
  setTheme: (theme: Theme) => void

  // View preferences
  defaultViewMode: DefaultViewMode
  setDefaultViewMode: (mode: DefaultViewMode) => void

  // Query preferences
  queryHistoryLimit: number
  setQueryHistoryLimit: (limit: number) => void
  autoExecuteQuery: boolean
  setAutoExecuteQuery: (enabled: boolean) => void

  // Visualization limits
  maxNodesForGraph: number
  maxEdgesForGraph: number
  setMaxNodesForGraph: (max: number) => void
  setMaxEdgesForGraph: (max: number) => void

  // Table view preferences
  tablePageSize: number
  setTablePageSize: (size: number) => void

  // Graph view preferences
  defaultLayout: 'force' | 'hierarchical' | 'radial' | 'grid' | 'random'
  setDefaultLayout: (layout: 'force' | 'hierarchical' | 'radial' | 'grid' | 'random') => void

  // Export preferences
  exportImageFormat: 'png' | 'svg'
  setExportImageFormat: (format: 'png' | 'svg') => void
  exportImageWidth: number
  exportImageHeight: number
  setExportImageSize: (width: number, height: number) => void

  // Reset to defaults
  resetSettings: () => void
}

const defaultSettings = {
  theme: 'light' as Theme,
  defaultViewMode: 'auto' as DefaultViewMode,
  queryHistoryLimit: 50,
  autoExecuteQuery: false,
  maxNodesForGraph: 5000,
  maxEdgesForGraph: 10000,
  tablePageSize: 50,
  defaultLayout: 'force' as const,
  exportImageFormat: 'png' as const,
  exportImageWidth: 1920,
  exportImageHeight: 1080,
}

export const useSettingsStore = create<AppSettings>()(
  persist(
    (set) => ({
      ...defaultSettings,

      setTheme: (theme) => set({ theme }),

      setDefaultViewMode: (mode) => set({ defaultViewMode: mode }),

      setQueryHistoryLimit: (limit) => set({ queryHistoryLimit: Math.max(10, Math.min(500, limit)) }),

      setAutoExecuteQuery: (enabled) => set({ autoExecuteQuery: enabled }),

      setMaxNodesForGraph: (max) => set({ maxNodesForGraph: Math.max(100, Math.min(100000, max)) }),

      setMaxEdgesForGraph: (max) => set({ maxEdgesForGraph: Math.max(100, Math.min(200000, max)) }),

      setTablePageSize: (size) => set({ tablePageSize: Math.max(10, Math.min(1000, size)) }),

      setDefaultLayout: (layout) => set({ defaultLayout: layout }),

      setExportImageFormat: (format) => set({ exportImageFormat: format }),

      setExportImageSize: (width, height) =>
        set({
          exportImageWidth: Math.max(100, Math.min(10000, width)),
          exportImageHeight: Math.max(100, Math.min(10000, height)),
        }),

      resetSettings: () => set(defaultSettings),
    }),
    {
      name: 'kotte-settings',
      version: 1,
    }
  )
)


