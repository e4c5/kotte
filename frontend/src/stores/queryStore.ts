/**
 * Query execution state management with multi-tab support.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { queryAPI, type QueryExecuteRequest, type QueryExecuteResponse } from '../services/query'
import type { GraphEdge, GraphNode } from '../services/graph'
import { mergeGraphElements as mergeGraphElementsPure } from '../utils/graphMerge'

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
  /**
   * Snapshot of `result.graph_elements` taken when the user invokes
   * `isolateNeighborhood` (ROADMAP A11 phase 3). Non-null while the canvas
   * is showing the isolated subgraph; cleared by `restoreGraphElements`,
   * which copies the snapshot back onto `result.graph_elements`.
   *
   * Stored as plain JSON-shaped data (not a typed alias of
   * `QueryExecuteResponse['graph_elements']`) because zustand's `persist`
   * middleware drops `result` on rehydrate; keeping the snapshot loosely
   * typed avoids dragging the heavy result type onto every persisted tab.
   */
  previousGraphElements?: NonNullable<QueryExecuteResponse['graph_elements']> | null
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
  executeQuery: (
    tabId: string,
    graph: string,
    query: string,
    params?: Record<string, unknown>,
    forVisualization?: boolean,
    mutationConfirmed?: boolean
  ) => Promise<void>
  /** Stream a query, accumulating rows into the tab's result incrementally. */
  streamQuery: (
    tabId: string,
    graph: string,
    query: string,
    params?: Record<string, unknown>,
    mutationConfirmed?: boolean
  ) => Promise<void>
  cancelQuery: (tabId: string) => Promise<void>

  // History
  addToHistory: (query: string) => void
  clearError: (tabId: string) => void

  // Graph operations
  mergeGraphElements: (
    tabId: string,
    nodes: GraphNode[],
    edges: GraphEdge[]
  ) => { addedNodeIds: string[]; addedEdgeIds: string[] }
  updateResult: (tabId: string, updater: (result: QueryExecuteResponse | null) => QueryExecuteResponse | null) => void
  /**
   * ROADMAP A11 phase 3 — explicit reversible "isolate" mode. Snapshots
   * the current `tab.result.graph_elements` into `previousGraphElements`,
   * then rewrites the canvas to show only `nodeId` and its incident edges
   * (and the endpoints of those edges) from the **current** canvas. No API
   * call — this is a deterministic client-side filter so it can't fail or
   * surprise the user with new data.
   */
  isolateNeighborhood: (tabId: string, nodeId: string) => void
  /**
   * Restores the snapshot taken by `isolateNeighborhood` and clears it.
   * No-op if no snapshot exists.
   */
  restoreGraphElements: (tabId: string) => void

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

// AbortControllers are not serialisable so they live outside zustand/persist.
const _streamAbortControllers = new Map<string, AbortController>()

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
          const tabId = `tab-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
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

        executeQuery: async (
          tabId: string,
          graph: string,
          query: string,
          params?: Record<string, unknown>,
          forVisualization: boolean = false,
          mutationConfirmed: boolean = false
        ) => {
          get().updateTab(tabId, { loading: true, error: null, requestId: null, graph })

          try {
            const request: QueryExecuteRequest = {
              graph,
              cypher: query,
              params: params || {},
              for_visualization: forVisualization,
              mutation_confirmed: mutationConfirmed,
            }
            const result = await queryAPI.execute(request)

            // A wholesale result replacement invalidates any in-flight isolate
            // snapshot — `previousGraphElements` references nodes/edges from
            // the *previous* result version, so leaving it set would make the
            // breadcrumb's "restore" splice stale data into the new result.
            // Scope the snapshot to one concrete result version by clearing it
            // here (covers re-execute on the same tab, graph switches via
            // executeQuery, and any future caller that replaces `result`).
            get().updateTab(tabId, {
              result,
              previousGraphElements: null,
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

        streamQuery: async (
          tabId: string,
          graph: string,
          query: string,
          params?: Record<string, unknown>,
          _mutationConfirmed: boolean = false
        ) => {
          // Abort any in-flight stream for this tab before starting a new one.
          _streamAbortControllers.get(tabId)?.abort()
          const controller = new AbortController()
          _streamAbortControllers.set(tabId, controller)

          get().updateTab(tabId, {
            loading: true,
            error: null,
            requestId: null,
            graph,
            result: null,
            previousGraphElements: null,
          })

          let accumulatedRows: unknown[] = []
          let columns: string[] = []

          try {
            for await (const chunk of queryAPI.stream(
              { graph, cypher: query, params: params || {} },
              controller.signal
            )) {
              if (controller.signal.aborted) break

              if (columns.length === 0 && chunk.columns.length > 0) {
                columns = chunk.columns
              }
              accumulatedRows = accumulatedRows.concat(chunk.rows)

              // Update the tab with accumulated rows so TableView re-renders incrementally.
              get().updateTab(tabId, {
                result: {
                  columns,
                  rows: accumulatedRows as QueryExecuteResponse['rows'],
                  row_count: accumulatedRows.length,
                  request_id: '',
                },
                loading: chunk.has_more,
                lastActivity: Date.now(),
              })
            }

            if (!controller.signal.aborted) {
              get().updateTab(tabId, { loading: false, requestId: null })
              get().addToHistory(query)
            }
          } catch (error) {
            if (controller.signal.aborted) {
              get().updateTab(tabId, { loading: false, requestId: null })
              return
            }
            const message = error instanceof Error ? error.message : 'Streaming failed'
            get().updateTab(tabId, { error: message, loading: false, requestId: null })
          } finally {
            _streamAbortControllers.delete(tabId)
          }
        },

        cancelQuery: async (tabId: string) => {
          // Abort any in-progress stream first (no round-trip needed).
          const ctrl = _streamAbortControllers.get(tabId)
          if (ctrl) {
            ctrl.abort()
            _streamAbortControllers.delete(tabId)
            get().updateTab(tabId, { loading: false, requestId: null })
            return
          }

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
            return { addedNodeIds: [], addedEdgeIds: [] }
          }

          const existing = {
            nodes: (tab.result.graph_elements.nodes ?? []) as GraphNode[],
            edges: (tab.result.graph_elements.edges ?? []) as GraphEdge[],
          }
          const merged = mergeGraphElementsPure(existing, { nodes: newNodes, edges: newEdges })

          if (merged.added.nodeIds.length === 0 && merged.added.edgeIds.length === 0) {
            return { addedNodeIds: [], addedEdgeIds: [] }
          }

          get().updateResult(tabId, (currentResult) => {
            if (!currentResult) return null
            return {
              ...currentResult,
              // The QueryExecuteResponse type narrowly types edge endpoints as
              // strings, but D3's force layout may have already mutated existing
              // edges to hold GraphNode references. The pre-refactor code
              // preserved that mutation too — the cast just makes the long-
              // standing reality explicit.
              graph_elements: {
                ...currentResult.graph_elements,
                nodes: merged.nodes,
                edges: merged.edges,
              } as QueryExecuteResponse['graph_elements'],
              stats: {
                ...currentResult.stats,
                nodes_extracted: merged.nodes.length,
                edges_extracted: merged.edges.length,
              },
            }
          })

          return { addedNodeIds: merged.added.nodeIds, addedEdgeIds: merged.added.edgeIds }
        },

        isolateNeighborhood: (tabId: string, nodeId: string) => {
          const tab = get().tabs.find((t) => t.id === tabId)
          if (!tab?.result?.graph_elements) return

          const ge = tab.result.graph_elements
          const nodes = (ge.nodes ?? []) as GraphNode[]
          const edges = (ge.edges ?? []) as GraphEdge[]

          // Only filter once — re-isolating without restoring first would
          // overwrite the snapshot with the already-narrowed canvas, making
          // restore a no-op. Bail out (the breadcrumb is the user's path back).
          if (tab.previousGraphElements) return

          // The clicked node + every node directly connected to it on the
          // current canvas. Edges are filtered to those whose endpoints are
          // both in the kept set; this lets the existing `GraphView`
          // simulation render the subgraph without further changes.
          const incidentEdges = edges.filter((e) => {
            const s = typeof e.source === 'string' ? e.source : e.source.id
            const t = typeof e.target === 'string' ? e.target : e.target.id
            return s === nodeId || t === nodeId
          })
          const keepNodeIds = new Set<string>([nodeId])
          for (const e of incidentEdges) {
            const s = typeof e.source === 'string' ? e.source : e.source.id
            const t = typeof e.target === 'string' ? e.target : e.target.id
            keepNodeIds.add(s)
            keepNodeIds.add(t)
          }
          const keptNodes = nodes.filter((n) => keepNodeIds.has(n.id))

          // Defensive: a half-merged result can hold an edge whose endpoint is
          // not in `nodes[]`. `keptNodes` is the intersection with `nodes[]`,
          // so re-filter `incidentEdges` against the actually-kept set to
          // avoid emitting dangling edges that the simulation/renderer would
          // either drop or mis-render.
          const keptNodeIdSet = new Set(keptNodes.map((n) => n.id))
          const keptEdges = incidentEdges.filter((e) => {
            const s = typeof e.source === 'string' ? e.source : e.source.id
            const t = typeof e.target === 'string' ? e.target : e.target.id
            return keptNodeIdSet.has(s) && keptNodeIdSet.has(t)
          })

          // If the clicked node has no edges on the current canvas we still
          // isolate (the user gets just that node back). They can step out
          // via the breadcrumb.
          get().updateTab(tabId, {
            previousGraphElements: ge as NonNullable<QueryExecuteResponse['graph_elements']>,
          })
          get().updateResult(tabId, (currentResult) => {
            if (!currentResult) return null
            return {
              ...currentResult,
              graph_elements: {
                ...currentResult.graph_elements,
                nodes: keptNodes,
                edges: keptEdges,
              } as QueryExecuteResponse['graph_elements'],
              stats: {
                ...currentResult.stats,
                nodes_extracted: keptNodes.length,
                edges_extracted: keptEdges.length,
              },
            }
          })
        },

        restoreGraphElements: (tabId: string) => {
          const tab = get().tabs.find((t) => t.id === tabId)
          if (!tab?.previousGraphElements) return
          const snapshot = tab.previousGraphElements
          get().updateResult(tabId, (currentResult) => {
            if (!currentResult) return null
            return {
              ...currentResult,
              graph_elements: snapshot,
              stats: {
                ...currentResult.stats,
                nodes_extracted: snapshot.nodes?.length ?? 0,
                edges_extracted: snapshot.edges?.length ?? 0,
              },
            }
          })
          get().updateTab(tabId, { previousGraphElements: null })
        },

        // Legacy support
        clearResult: () => {
          const activeTab = getActiveTab()
          if (activeTab) {
            get().updateTab(activeTab.id, {
              result: null,
              error: null,
              previousGraphElements: null,
            })
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
          // `previousGraphElements` is a snapshot of `result` (which we're
          // dropping above) so it must drop with it — otherwise restoring an
          // isolate would resurrect a snapshot whose live counterpart is gone.
          previousGraphElements: null,
        })),
        activeTabId: state.activeTabId,
      }),
    }
  )
)
