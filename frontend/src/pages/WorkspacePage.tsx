import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'
import { useQueryStore } from '../stores/queryStore'
import { useGraphStore } from '../stores/graphStore'
import { useAuthStore } from '../stores/authStore'
import { useSettingsStore } from '../stores/settingsStore'
import QueryEditor, { getQueryParams } from '../components/QueryEditor'
import MetadataSidebar from '../components/MetadataSidebar'
import InspectorPanel from '../components/InspectorPanel'
import SettingsModal from '../components/SettingsModal'
import TabBar from '../components/TabBar'
import ResultTab from '../components/ResultTab'
import { graphAPI } from '../services/graph'
import { getNodeLabelColor } from '../utils/nodeColors'

// Builds the human-readable reason a result cannot be visualised, or null when
// the active result fits within the configured node/edge caps. Extracted to
// avoid nested ternaries (Sonar S3358) and to keep the render path readable.
function computeVizDisabledReason(
  nodes: number,
  edges: number,
  maxNodes: number,
  maxEdges: number,
): string | null {
  if (nodes > maxNodes) {
    return `Result has ${nodes.toLocaleString()} nodes, exceeding the visualization limit of ${maxNodes.toLocaleString()}. Switch to Table view, refine the query, or raise the limit in Settings.`
  }
  if (edges > maxEdges) {
    return `Result has ${edges.toLocaleString()} edges, exceeding the visualization limit of ${maxEdges.toLocaleString()}. Switch to Table view, refine the query, or raise the limit in Settings.`
  }
  return null
}

export default function WorkspacePage() {
  const navigate = useNavigate()
  const { status, refreshStatus, disconnect } = useSessionStore()
  const { logout: authLogout, checkAuth } = useAuthStore()
  const {
    tabs,
    activeTabId,
    query,
    params,
    setParams,
    setQuery,
    setCurrentGraph,
    createTab,
    closeTab,
    setActiveTab,
    updateTab,
    pinTab,
    unpinTab,
    executeQuery,
    streamQuery,
    cancelQuery,
    clearError,
    history,
    mergeGraphElements,
    updateResult,
    isolateNeighborhood,
    restoreGraphElements,
    currentGraph,
    loading,
    error,
  } = useQueryStore()

  const { tablePageSize, defaultLayout, maxNodesForGraph, maxEdgesForGraph } = useSettingsStore()
  const [showSettings, setShowSettings] = useState(false)
  const [expanding, setExpanding] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mutationConfirmPending, setMutationConfirmPending] = useState(false)
  const {
    setSelectedNode,
    setSelectedEdge,
    selectedNode,
    selectedEdge,
    setLayout,
    setCameraFocusAnchorIds,
  } = useGraphStore()

  // Mount-only initializer: ensure exactly one tab exists and one is active.
  // Wiring tabs/activeTabId/createTab/setActiveTab as deps would re-run this on
  // every tab change and is unnecessary — the body is idempotent against the
  // initial mount only.
  useEffect(() => {
    if (tabs.length === 0) {
      createTab('Query 1')
    } else if (!activeTabId) {
      setActiveTab(tabs[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Apply default layout only when the user changes it in Settings, not when they change the dropdown
  const isFirstLayoutSync = useRef(true)
  useEffect(() => {
    if (isFirstLayoutSync.current) {
      isFirstLayoutSync.current = false
      return
    }
    setLayout(defaultLayout)
  }, [defaultLayout, setLayout])

  useEffect(() => {
    checkAuth().then(() => {
      const isAuthenticated = useAuthStore.getState().authenticated
      if (!isAuthenticated) {
        navigate('/login')
      } else {
        refreshStatus()
      }
    })
  }, [navigate, checkAuth, refreshStatus])

  useEffect(() => {
    if (status && !status.connected) {
      navigate('/')
    }
  }, [status, navigate])

  const handleDisconnect = async () => {
    await disconnect()
    await authLogout()
    navigate('/login')
  }

  const MUTATION_RE = /\b(CREATE|DELETE|SET|REMOVE|MERGE|DETACH)\b/i

  function applyGraphViewMode(tabId: string) {
    const { tabs: latestTabs } = useQueryStore.getState()
    const tab = latestTabs.find((t) => t.id === tabId)
    if (!tab?.result) return
    const { result } = tab
    if (result.visualization_warning) {
      updateTab(tabId, { viewMode: 'table' })
    } else if (result.graph_elements) {
      const hasElements =
        (result.graph_elements.nodes?.length || 0) > 0 ||
        (result.graph_elements.edges?.length || 0) > 0
      updateTab(tabId, { viewMode: hasElements ? 'graph' : 'table' })
    }
  }

  const runQuery = async (mutationConfirmed = false) => {
    if (!activeTabId || !currentGraph || !query.trim()) return
    const parseResult = getQueryParams(params)
    if (!parseResult.ok) return
    const currentTab = tabs.find((t) => t.id === activeTabId)
    const wantsGraph = currentTab?.viewMode === 'graph'
    try {
      if (wantsGraph || mutationConfirmed) {
        await executeQuery(activeTabId, currentGraph, query, parseResult.value, true, mutationConfirmed)
        if (wantsGraph) {
          applyGraphViewMode(activeTabId)
        }
      } else {
        await streamQuery(activeTabId, currentGraph, query, parseResult.value, mutationConfirmed)
      }
    } catch (err) {
      // Primary error state is set by the store; log here for debuggability.
      console.error('Query execution error:', err)
    }
  }

  const handleExecute = async () => {
    if (!activeTabId || !currentGraph || !query.trim()) return
    const parseResult = getQueryParams(params)
    if (!parseResult.ok) return
    if (MUTATION_RE.test(query)) {
      setMutationConfirmPending(true)
      return
    }
    await runQuery(false)
  }

  const handleMutationConfirm = async () => {
    setMutationConfirmPending(false)
    await runQuery(true)
  }

  const handleGraphSelect = (graphName: string) => {
    setCurrentGraph(graphName)
    if (activeTabId) {
      updateTab(activeTabId, { graph: graphName, result: null })
    }
  }

  const handleQueryTemplate = (templateQuery: string, templateParams?: string) => {
    setQuery(templateQuery)
    if (templateParams !== undefined) {
      setParams(templateParams)
    }
  }

  const handleTabClick = (tabId: string) => {
    setActiveTab(tabId)
  }

  const handleTabClose = (tabId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (tabs.length <= 1) {
      updateTab(tabId, {
        query: '',
        result: null,
        error: null,
        previousGraphElements: null,
      })
      return
    }
    closeTab(tabId)
  }

  const handleNewTab = () => {
    const newTabId = createTab()
    setActiveTab(newTabId)
  }

  const handleExpandNode = async (
    nodeId: string,
    options?: { depth?: number; limit?: number; edge_labels?: string[]; direction?: 'in' | 'out' | 'both' },
  ): Promise<{ addedNodeIds: string[]; addedEdgeIds: string[]; truncated: boolean; total_neighbours: number } | null> => {
    if (!activeTabId || !currentGraph || expanding) return null
    setExpanding(true)
    try {
      const expandResult = await graphAPI.expandNode(currentGraph, nodeId, {
        depth: options?.depth ?? 1,
        limit: options?.limit ?? 100,
        edge_labels: options?.edge_labels,
        direction: options?.direction ?? 'both',
      })
      const merged = mergeGraphElements(activeTabId, expandResult.nodes, expandResult.edges)
      return {
        ...merged,
        truncated: expandResult.truncated,
        total_neighbours: expandResult.total_neighbours,
      }
    } catch (err) {
      console.error('Failed to expand node:', err)
      return null
    } finally {
      setExpanding(false)
    }
  }

  // Double-clicking a node is a discoverable shortcut for the right-click
  // "Expand neighborhood" action: it merges the node's first-level neighbours
  // into the current view (additive — never destructive). See ROADMAP.md A11.
  // Phase 2 also focuses the camera on `{clicked} ∪ addedNodeIds` so the user
  // sees what they just expanded instead of having the whole canvas re-fit.
  // Typed against the structural minimum so it accepts both the GraphView and
  // services/graph GraphNode shapes without coupling the page to either.
  const handleDoubleClickNode = async (node: { id: string }) => {
    // `cameraFocusAnchorIds` is a global graphStore value consumed by the
    // currently-mounted GraphView. If the user switches tabs while the expand
    // is in flight, applying the focus would zoom the *other* tab's canvas to
    // anchors that don't belong to it. Capture the originating tab id and
    // bail if the active tab moved on by the time the await resolves. We use
    // `getState()` (not the closed-over `activeTabId`) to read the *current*
    // value, since a setState may have happened during the await.
    const requestTabId = activeTabId
    const merged = await handleExpandNode(node.id)
    if (!merged || !requestTabId) return
    if (useQueryStore.getState().activeTabId !== requestTabId) return
    // Always include the clicked node in the focus union so a no-op expand
    // (node already had all its neighbours on canvas) still recentres on it.
    setCameraFocusAnchorIds([node.id, ...merged.addedNodeIds])
  }

  const handleNodeIsolate = (nodeId: string) => {
    if (!activeTabId) return
    isolateNeighborhood(activeTabId, nodeId)
  }

  const handleRestoreFullResult = () => {
    if (!activeTabId) return
    restoreGraphElements(activeTabId)
  }

  const handleDeleteNode = async (nodeId: string) => {
    if (!activeTabId || !currentGraph) return
    const confirmMessage =
      'Are you sure you want to delete this node?\n\n' +
      'This will delete the node and all its relationships.\n' +
      'This action cannot be undone.'
    if (!confirm(confirmMessage)) return

    try {
      await graphAPI.deleteNode(currentGraph, nodeId, { detach: true })
      const tab = tabs.find((t) => t.id === activeTabId)
      if (tab?.result?.graph_elements) {
        const updatedNodes =
          tab.result.graph_elements.nodes?.filter((n) => n.id !== nodeId) || []
        const updatedEdges =
          tab.result.graph_elements.edges?.filter(
            (e) => e.source !== nodeId && e.target !== nodeId
          ) || []
        updateResult(activeTabId, (currentResult) => {
          if (!currentResult) return null
          return {
            ...currentResult,
            graph_elements: { nodes: updatedNodes, edges: updatedEdges },
          }
        })
      }
      setSelectedNode(null)
    } catch (err) {
      console.error('Failed to delete node:', err)
      alert('Failed to delete node. Please try again.')
    }
  }

  const handleTabViewModeChange = (tabId: string, mode: 'graph' | 'table') => {
    updateTab(tabId, { viewMode: mode })
  }

  const handleTabExportReady = (_tabId: string, _exportFn: () => Promise<void>) => {}

  const closeInspector = () => {
    setSelectedNode(null)
    setSelectedEdge(null)
  }

  // Derive viz state up here (before the early `return` for !status.connected)
  // so the `useEffect` below it isn't called conditionally.
  const activeTab = tabs.find((t) => t.id === activeTabId)
  const graphNodes = activeTab?.result?.graph_elements?.nodes ?? []
  const graphEdges = activeTab?.result?.graph_elements?.edges ?? []
  const inspectorOpen = !!selectedNode || !!selectedEdge

  // Client-side viz limit (ROADMAP A5). The 5000/10000 defaults in
  // `settingsStore` were never enforced, so an accidental 50k-node query would
  // freeze the canvas. We compute a single human-readable reason here, force
  // the tab into table view if it's currently graph, and feed the same string
  // to ResultTab which uses it to disable the Graph button + render a banner.
  const activeNodeCount = graphNodes.length
  const activeEdgeCount = graphEdges.length
  const vizDisabledReason: string | null = computeVizDisabledReason(
    activeNodeCount,
    activeEdgeCount,
    maxNodesForGraph,
    maxEdgesForGraph,
  )

  const activeTabId_ = activeTab?.id
  const activeTabViewMode = activeTab?.viewMode
  useEffect(() => {
    if (vizDisabledReason && activeTabId_ && activeTabViewMode === 'graph') {
      updateTab(activeTabId_, { viewMode: 'table' })
    }
  }, [vizDisabledReason, activeTabId_, activeTabViewMode, updateTab])

  if (!status || !status.connected) {
    return (
      <div className="h-screen flex items-center justify-center bg-white text-zinc-600 dark:bg-zinc-950 dark:text-zinc-400">
        Loading...
      </div>
    )
  }

  return (
    <div className="relative h-screen w-full overflow-hidden bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      {/* Header: slim, fixed — offset left by sidebar width so it does not sit under the sidebar */}
      <header
        className={`fixed top-0 right-0 h-12 flex items-center justify-between px-4 bg-white/95 border-b border-zinc-200 dark:bg-zinc-900/95 dark:border-zinc-800 z-10 shrink-0 transition-[left] duration-300 ${
          sidebarCollapsed ? 'left-12' : 'left-64'
        }`}
      >
        <div className="flex items-center gap-4 min-w-0">
          <span className="font-semibold shrink-0 text-zinc-900 dark:text-zinc-100">Kotte</span>
          <span className="text-sm truncate text-zinc-500 dark:text-zinc-500">
            {status.database} @ {status.host}:{status.port}
          </span>
          {tabs.length > 0 && (
            <TabBar
              tabs={tabs}
              activeTabId={activeTabId}
              onTabClick={handleTabClick}
              onTabClose={handleTabClose}
              onNewTab={handleNewTab}
              onTabPin={pinTab}
              onTabUnpin={unpinTab}
            />
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* ROADMAP A1: discoverable settings entry. Previously the modal could
              only be opened from a buried banner inside the viz limit warning. */}
          <button
            type="button"
            onClick={() => setShowSettings(true)}
            className="p-1.5 rounded-lg border border-zinc-300 text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100 transition-colors"
            aria-label="Open settings"
            title="Settings"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
          <button
            type="button"
            onClick={handleDisconnect}
            className="px-3 py-1.5 text-sm rounded-lg border border-zinc-300 text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100 transition-colors"
            aria-label="Disconnect from database"
          >
            Disconnect
          </button>
        </div>
      </header>

      {/* Main content: query editor + results, offset by header and sidebar */}
      <div
        className={`absolute right-0 bottom-0 transition-[left] duration-300 ${
          sidebarCollapsed ? 'left-12' : 'left-64'
        }`}
        style={{ top: '3rem' }}
      >
        <div className="flex h-full flex-col">
          {/* Query bar */}
          <div className="shrink-0 px-3 py-2 bg-white border-b border-zinc-200 dark:bg-zinc-950 dark:border-zinc-800">
            <QueryEditor
              value={query}
              onChange={setQuery}
              params={params}
              onParamsChange={setParams}
              onExecute={handleExecute}
              onCancel={() => activeTabId && cancelQuery(activeTabId)}
              loading={loading}
              history={history}
            />
          </div>

          {/* Canvas layer: full-size result area (graph / table) */}
          <div className="flex-1 min-h-0">
            {activeTab ? (
              <ResultTab
                tab={activeTab}
                tablePageSize={tablePageSize}
                vizDisabledReason={vizDisabledReason}
                onOpenSettings={() => setShowSettings(true)}
                onViewModeChange={(mode) => handleTabViewModeChange(activeTab.id, mode)}
                onNodeExpand={async (id, options) => {
                  const result = await handleExpandNode(id, options)
                  if (!result) return null
                  return { truncated: result.truncated, total_neighbours: result.total_neighbours }
                }}
                onNodeDelete={handleDeleteNode}
                onNodeSelect={(node) => setSelectedNode(node.id)}
                onNodeDoubleClick={handleDoubleClickNode}
                onEdgeSelect={(edge) => setSelectedEdge(edge.id)}
                onNodeIsolate={handleNodeIsolate}
                onRestoreFullResult={handleRestoreFullResult}
                onExportReady={(exportFn) => handleTabExportReady(activeTab.id, exportFn)}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-zinc-500">
                No active tab. Create a new tab to start querying.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mutation confirmation modal */}
      {mutationConfirmPending && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-sm rounded-xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl">
            <h2 className="mb-2 text-base font-semibold text-zinc-100">Confirm mutating query</h2>
            <p className="mb-4 text-sm text-zinc-400">
              This query contains write operations (<span className="font-mono text-amber-400">CREATE</span>,{' '}
              <span className="font-mono text-amber-400">DELETE</span>,{' '}
              <span className="font-mono text-amber-400">SET</span>,{' '}
              <span className="font-mono text-amber-400">MERGE</span>, etc.) and will modify the
              graph. Proceed?
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setMutationConfirmPending(false)}
                className="px-4 py-2 rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800 text-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleMutationConfirm}
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium"
              >
                Yes, proceed
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error toast */}
      {error && (
        <div className="absolute left-1/2 top-24 -translate-x-1/2 z-30 max-w-xl w-[90%] px-4 py-3 rounded-lg bg-red-900/90 border border-red-700 text-red-100 text-sm flex items-center gap-3">
          <span className="flex-1 break-all">
            <strong>Error:</strong> {error}
          </span>
          <button
            type="button"
            onClick={() => activeTabId && clearError(activeTabId)}
            className="shrink-0 p-1 rounded hover:bg-red-800"
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {/* Left schema sidebar — controlled so layout stays in sync when e.g. Graph Controls open */}
      <MetadataSidebar
        currentGraph={currentGraph ?? undefined}
        onGraphSelect={handleGraphSelect}
        onQueryTemplate={handleQueryTemplate}
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />

      {/* Right inspector panel */}
      <InspectorPanel
        isOpen={inspectorOpen}
        onClose={closeInspector}
        nodes={graphNodes}
        edges={graphEdges}
        selectedNodeId={selectedNode}
        selectedEdgeId={selectedEdge}
        nodeLabelColor={getNodeLabelColor}
      />

      {showSettings && (
        <SettingsModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  )
}
