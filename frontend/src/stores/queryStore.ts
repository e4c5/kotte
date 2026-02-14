/**
 * Query execution state management.
 */

import { create } from 'zustand'
import { queryAPI, type QueryExecuteRequest, type QueryExecuteResponse } from '../services/query'

interface QueryState {
  // Current query
  query: string
  params: string
  currentGraph: string | null
  
  // Results
  result: QueryExecuteResponse | null
  loading: boolean
  error: string | null
  
  // History
  history: string[]
  historyIndex: number
  
  // Actions
  setQuery: (query: string) => void
  setParams: (params: string) => void
  setCurrentGraph: (graph: string) => void
  executeQuery: (graph: string, query: string, params?: Record<string, unknown>) => Promise<void>
  cancelQuery: (requestId: string) => Promise<void>
  addToHistory: (query: string) => void
  clearResult: () => void
  clearError: () => void
}

export const useQueryStore = create<QueryState>((set, get) => ({
  query: '',
  params: '{}',
  currentGraph: null,
  result: null,
  loading: false,
  error: null,
  history: [],
  historyIndex: -1,

  setQuery: (query: string) => set({ query }),
  
  setParams: (params: string) => set({ params }),
  
  setCurrentGraph: (graph: string) => set({ currentGraph: graph }),
  
  executeQuery: async (graph: string, query: string, params?: Record<string, unknown>) => {
    set({ loading: true, error: null })
    try {
      const request: QueryExecuteRequest = {
        graph,
        cypher: query,
        params: params || {},
      }
      const result = await queryAPI.execute(request)
      set({ result, loading: false })
      get().addToHistory(query)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Query execution failed'
      set({ error: message, loading: false })
      throw error
    }
  },
  
  cancelQuery: async (requestId: string) => {
    try {
      await queryAPI.cancel(requestId)
    } catch (error) {
      console.error('Failed to cancel query:', error)
    }
  },
  
  addToHistory: (query: string) => {
    const { history } = get()
    // Avoid duplicates
    const newHistory = [query, ...history.filter((q) => q !== query)].slice(0, 50)
    set({ history: newHistory })
  },
  
  clearResult: () => set({ result: null, error: null }),
  
  clearError: () => set({ error: null }),
}))

