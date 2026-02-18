/**
 * Query execution state management with multi-tab support.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { queryAPI, type QueryExecuteRequest, type QueryExecuteResponse } from '../services/query'

export interface QueryTab {
  id: string
  name: string
  query: string
  params: string
  graph: string | null
  result: QueryExecuteResponse | null
  loading: boolean
  error: string | null
  requestId: string | null
  viewMode: 'graph' | 'table'
  pinned: boolean
  createdAt: number
  lastActivity: number
}

interface QueryState {
  // Tabs
  tabs: QueryTab[]
  activeTabId: string | null
  
  // Current query (for backward compatibility and new tab creation)
  query: string
  params: string
  currentGraph: string | null
  
  // History
  history: string[]
  historyIndex: number
  
  // Actions
  setQuery: (query: string) => void
  setParams: (params: string) => void
  setCurrentGraph: (graph: string) => void
  
  // Tab management
  createTab: (name?: string) => string
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void
  updateTab: (tabId: string, updates: Partial<QueryTab>) => void
  pinTab: (tabId: string) => void
  unpinTab: (tabId: string) => void
  
  // Query execution (per tab)
  executeQuery: (tabId: string, graph: string, query: string, params?: Record<string, unknown>) => Promise<void>
  cancelQuery: (tabId: string) => Promise<void>
  
  // History
  addToHistory: (query: string) => void
  clearError: (tabId: string) => void
  
  // Graph operations
  mergeGraphElements: (tabId: string, nodes: Array<{id: string, label: string, properties: Record<string, unknown>, type: string}>, edges: Array<{id: string, label: string, source: string, target: string, properties: Record<string, unknown>, type: string}>) => void
  updateResult: (tabId: string, updater: (result: QueryExecuteResponse | null) => QueryExecuteResponse | null) => void
  
  // Legacy support (for components that haven't been updated)
  result: QueryExecuteResponse | null
  loading: boolean
  error: string | null
  currentRequestId: string | null
  clearResult: () => void
}

const generateTabName = (index: number): string => {
  return `Query ${index}`
}

export const useQueryStore = create<QueryState>()(
  persist(
    (set, get) => {
      // Helper to get active tab (internal use)
      const getActiveTab = (): QueryTab | null => {
        const { tabs, activeTabId } = get()
        if (!activeTabId) return null
        return tabs.find(t => t.id === activeTabId) || null
      }
      
      return {
        tabs: [],
        activeTabId: null,
        query: '',
        params: '{}',
        currentGraph: null,
        history: [],
        historyIndex: -1,
        result: null,
        loading: false,
        error: null,
        currentRequestId: null,

        setQuery: (query: string) => {
          const activeTab = getActiveTab()
          if (activeTab) {
            get().updateTab(activeTab.id, { query })
          }
          set({ query })
        },
        
        setParams: (params: string) => {
          const activeTab = getActiveTab()
          if (activeTab) {
            get().updateTab(activeTab.id, { params })
          }
          set({ params })
        },
        
        setCurrentGraph: (graph: string) => {
          const activeTab = getActiveTab()
          if (activeTab) {
            get().updateTab(activeTab.id, { graph })
          }
          set({ currentGraph: graph })
        },

        createTab: (name?: string) => {
          const { tabs } = get()
          const tabId = `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
          const tabNumber = tabs.length + 1
          const tabName = name || generateTabName(tabNumber)
          
          const newTab: QueryTab = {
            id: tabId,
            name: tabName,
            query: '',
            params: '{}',
            graph: null,
            result: null,
            loading: false,
            error: null,
            requestId: null,
            viewMode: 'graph',
            pinned: false,
            createdAt: Date.now(),
            lastActivity: Date.now(),
          }
          
          set({
            tabs: [...tabs, newTab],
            activeTabId: tabId,
          })
          
          return tabId
        },

        closeTab: (tabId: string) => {
          const { tabs, activeTabId } = get()
          const newTabs = tabs.filter(t => t.id !== tabId)
          
          // If closing active tab, switch to another
          let newActiveId = activeTabId
          if (activeTabId === tabId) {
            const closedIndex = tabs.findIndex(t => t.id === tabId)
            // Try to select tab to the right, then left, then first available
            if (closedIndex < newTabs.length) {
              newActiveId = newTabs[closedIndex].id
            } else if (newTabs.length > 0) {
              newActiveId = newTabs[newTabs.length - 1].id
            } else {
              newActiveId = null
            }
          }
          
          set({
            tabs: newTabs,
            activeTabId: newActiveId,
          })
        },

        setActiveTab: (tabId: string) => {
          const { tabs } = get()
          const tab = tabs.find(t => t.id === tabId)
          if (tab) {
            // Update last activity
            get().updateTab(tabId, { lastActivity: Date.now() })
            // Sync legacy state
            set({
              activeTabId: tabId,
              query: tab.query,
              params: tab.params,
              currentGraph: tab.graph,
              result: tab.result,
              loading: tab.loading,
              error: tab.error,
              currentRequestId: tab.requestId,
            })
          }
        },

        updateTab: (tabId: string, updates: Partial<QueryTab>) => {
          const { tabs, activeTabId } = get()
          const newTabs = tabs.map(t => 
            t.id === tabId ? { ...t, ...updates } : t
          )
          
          set({ tabs: newTabs })
          
          // Update legacy state if this is the active tab
          if (activeTabId === tabId) {
            const updatedTab = newTabs.find(t => t.id === tabId)
            if (updatedTab) {
              set({
                query: updatedTab.query,
                params: updatedTab.params,
                currentGraph: updatedTab.graph,
                result: updatedTab.result,
                loading: updatedTab.loading,
                error: updatedTab.error,
                currentRequestId: updatedTab.requestId,
              })
            }
          }
        },

        pinTab: (tabId: string) => {
          get().updateTab(tabId, { pinned: true })
        },

        unpinTab: (tabId: string) => {
          get().updateTab(tabId, { pinned: false })
        },
        
        executeQuery: async (tabId: string, graph: string, query: string, params?: Record<string, unknown>) => {
          get().updateTab(tabId, { loading: true, error: null, requestId: null, graph })
          
          try {
            const request: QueryExecuteRequest = {
              graph,
              cypher: query,
              params: params || {},
            }
            const result = await queryAPI.execute(request)
            
            get().updateTab(tabId, {
              result,
              loading: false,
              requestId: result.request_id,
              query,
              params: JSON.stringify(params || {}),
              lastActivity: Date.now(),
            })
            
            get().addToHistory(query)
          } catch (error) {
            const message = error instanceof Error ? error.message : 'Query execution failed'
            get().updateTab(tabId, {
              error: message,
              loading: false,
              requestId: null,
            })
            throw error
          }
        },
        
        cancelQuery: async (tabId: string) => {
          const tab = get().tabs.find(t => t.id === tabId)
          if (!tab || !tab.requestId) {
            return
          }
          
          try {
            await queryAPI.cancel(tab.requestId)
            get().updateTab(tabId, { loading: false, requestId: null })
          } catch (error) {
            console.error('Failed to cancel query:', error)
            get().updateTab(tabId, { loading: false, requestId: null })
          }
        },
        
        addToHistory: (query: string) => {
          const { history } = get()
          const newHistory = [query, ...history.filter((q) => q !== query)].slice(0, 50)
          set({ history: newHistory })
        },
        
        clearError: (tabId: string) => {
          get().updateTab(tabId, { error: null })
        },
        
        updateResult: (tabId: string, updater) => {
          const tab = get().tabs.find(t => t.id === tabId)
          if (!tab) return
          
          const updated = updater(tab.result)
          get().updateTab(tabId, { result: updated })
        },
        
        mergeGraphElements: (tabId: string, newNodes, newEdges) => {
          const tab = get().tabs.find(t => t.id === tabId)
          if (!tab?.result?.graph_elements) {
            return
          }
          
          const existingNodeIds = new Set(tab.result.graph_elements.nodes?.map(n => n.id) || [])
          const mergedNodes = [...(tab.result.graph_elements.nodes || [])]
          for (const node of newNodes) {
            if (!existingNodeIds.has(node.id)) {
              mergedNodes.push(node)
              existingNodeIds.add(node.id)
            }
          }
          
          const existingEdgeIds = new Set(tab.result.graph_elements.edges?.map(e => e.id) || [])
          const mergedEdges = [...(tab.result.graph_elements.edges || [])]
          for (const edge of newEdges) {
            if (!existingEdgeIds.has(edge.id)) {
              mergedEdges.push(edge)
              existingEdgeIds.add(edge.id)
            }
          }
          
          get().updateResult(tabId, (currentResult) => {
            if (!currentResult) return null
            return {
              ...currentResult,
              graph_elements: {
                nodes: mergedNodes,
                edges: mergedEdges,
              },
              stats: {
                ...currentResult.stats,
                nodes_extracted: mergedNodes.length,
                edges_extracted: mergedEdges.length,
              },
            }
          })
        },
        
        // Legacy support
        clearResult: () => {
          const activeTab = getActiveTab()
          if (activeTab) {
            get().updateTab(activeTab.id, { result: null, error: null })
          }
        },
      }
    },
    {
      name: 'kotte-query-store',
      partialize: (state: QueryState) => ({
        history: state.history,
        tabs: state.tabs.map((t: QueryTab) => ({
          ...t,
          result: null, // Don't persist results
          loading: false,
          error: null,
          requestId: null,
        })),
        activeTabId: state.activeTabId,
      }),
    }
  )
)
