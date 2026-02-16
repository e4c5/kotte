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
  currentRequestId: string | null  // For cancellation
  
  // History
  history: string[]
  historyIndex: number
  
  // Actions
  setQuery: (query: string) => void
  setParams: (params: string) => void
  setCurrentGraph: (graph: string) => void
  executeQuery: (graph: string, query: string, params?: Record<string, unknown>) => Promise<void>
  cancelQuery: () => Promise<void>
  addToHistory: (query: string) => void
  clearResult: () => void
  clearError: () => void
  mergeGraphElements: (nodes: Array<{id: string, label: string, properties: Record<string, unknown>, type: string}>, edges: Array<{id: string, label: string, source: string, target: string, properties: Record<string, unknown>, type: string}>) => void
  updateResult: (updater: (result: QueryExecuteResponse | null) => QueryExecuteResponse | null) => void
}

export const useQueryStore = create<QueryState>((set, get) => ({
  query: '',
  params: '{}',
  currentGraph: null,
  result: null,
  loading: false,
  error: null,
  currentRequestId: null,
  history: [],
  historyIndex: -1,

  setQuery: (query: string) => set({ query }),
  
  setParams: (params: string) => set({ params }),
  
  setCurrentGraph: (graph: string) => set({ currentGraph: graph }),
  
  executeQuery: async (graph: string, query: string, params?: Record<string, unknown>) => {
    set({ loading: true, error: null, currentRequestId: null })
    try {
      const request: QueryExecuteRequest = {
        graph,
        cypher: query,
        params: params || {},
      }
      const result = await queryAPI.execute(request)
      set({ 
        result, 
        loading: false,
        currentRequestId: result.request_id,
      })
      get().addToHistory(query)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Query execution failed'
      set({ error: message, loading: false, currentRequestId: null })
      throw error
    }
  },
  
  cancelQuery: async () => {
    const { currentRequestId } = get()
    if (!currentRequestId) {
      return
    }
    
    try {
      await queryAPI.cancel(currentRequestId)
      set({ loading: false, currentRequestId: null })
    } catch (error) {
      console.error('Failed to cancel query:', error)
      // Still stop loading even if cancel fails
      set({ loading: false, currentRequestId: null })
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
  
  updateResult: (updater) => {
    const { result } = get()
    const updated = updater(result)
    set({ result: updated })
  },
  
  mergeGraphElements: (newNodes, newEdges) => {
    const { result } = get()
    if (!result?.graph_elements) {
      return
    }
    
    // Merge nodes (avoid duplicates)
    const existingNodeIds = new Set(result.graph_elements.nodes?.map(n => n.id) || [])
    const mergedNodes = [...(result.graph_elements.nodes || [])]
    for (const node of newNodes) {
      if (!existingNodeIds.has(node.id)) {
        mergedNodes.push(node)
        existingNodeIds.add(node.id)
      }
    }
    
    // Merge edges (avoid duplicates)
    const existingEdgeIds = new Set(result.graph_elements.edges?.map(e => e.id) || [])
    const mergedEdges = [...(result.graph_elements.edges || [])]
    for (const edge of newEdges) {
      if (!existingEdgeIds.has(edge.id)) {
        mergedEdges.push(edge)
        existingEdgeIds.add(edge.id)
      }
    }
    
    // Update result with merged elements
    set({
      result: {
        ...result,
        graph_elements: {
          nodes: mergedNodes,
          edges: mergedEdges,
        },
        stats: {
          ...result.stats,
          nodes_extracted: mergedNodes.length,
          edges_extracted: mergedEdges.length,
        },
      },
    })
  },
}))

