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
    cancelQuery,
    clearError,
    history,
    mergeGraphElements,
    updateResult,
    currentGraph,
    loading,
    error,
  } = useQueryStore()

  const { tablePageSize, defaultLayout } = useSettingsStore()
  const [showSettings, setShowSettings] = useState(false)
  const [expanding, setExpanding] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const {
    setSelectedNode,
    setSelectedEdge,
    selectedNode,
    selectedEdge,
    layout,
    setLayout,
  } = useGraphStore()

  useEffect(() => {
    if (tabs.length === 0) {
      createTab('Query 1')
    } else if (!activeTabId) {
      setActiveTab(tabs[0].id)
    }
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

  const handleExecute = async () => {
    if (!activeTabId || !currentGraph || !query.trim()) {
      return
    }

    try {
      const queryParams = getQueryParams(params)
      const currentTab = tabs.find((t) => t.id === activeTabId)
      await executeQuery(
        activeTabId,
        currentGraph,
        query,
        queryParams,
        currentTab?.viewMode === 'graph'
      )

      const { tabs: latestTabs } = useQueryStore.getState()
      const tab = latestTabs.find((t) => t.id === activeTabId)
      if (tab?.result) {
        const result = tab.result
        if (result.graph_elements && !result.visualization_warning) {
          const hasElements =
            (result.graph_elements.nodes?.length || 0) > 0 ||
            (result.graph_elements.edges?.length || 0) > 0
          const newViewMode = hasElements ? 'graph' : 'table'
          updateTab(activeTabId, { viewMode: newViewMode })
        } else if (result.visualization_warning) {
          updateTab(activeTabId, { viewMode: 'table' })
        }
      }
    } catch (err) {
      // Error handled by store
    }
  }

  const handleGraphSelect = (graphName: string) => {
    setCurrentGraph(graphName)
    if (activeTabId) {
      updateTab(activeTabId, { graph: graphName, result: null })
    }
  }

  const handleQueryTemplate = (templateQuery: string) => {
    setQuery(templateQuery)
  }

  const handleTabClick = (tabId: string) => {
    setActiveTab(tabId)
  }

  const handleTabClose = (tabId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (tabs.length <= 1) {
      updateTab(tabId, { query: '', result: null, error: null })
      return
    }
    closeTab(tabId)
  }

  const handleNewTab = () => {
    const newTabId = createTab()
    setActiveTab(newTabId)
  }

  const handleExpandNode = async (nodeId: string) => {
    if (!activeTabId || !currentGraph || expanding) return
    setExpanding(true)
    try {
      const expandResult = await graphAPI.expandNode(currentGraph, nodeId, {
        depth: 1,
        limit: 100,
      })
      mergeGraphElements(activeTabId, expandResult.nodes, expandResult.edges)
    } catch (err) {
      console.error('Failed to expand node:', err)
    } finally {
      setExpanding(false)
    }
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

  if (!status || !status.connected) {
    return (
      <div className="h-screen bg-zinc-950 flex items-center justify-center text-zinc-400">
        Loading...
      </div>
    )
  }

  const activeTab = tabs.find((t) => t.id === activeTabId)
  const graphNodes = activeTab?.result?.graph_elements?.nodes ?? []
  const graphEdges = activeTab?.result?.graph_elements?.edges ?? []
  const inspectorOpen = !!selectedNode || !!selectedEdge

  return (
    <div className="relative h-screen w-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Header: slim, fixed — offset left by sidebar width so it does not sit under the sidebar */}
      <header
        className={`fixed top-0 right-0 h-12 flex items-center justify-between px-4 bg-zinc-900/95 border-b border-zinc-800 z-10 shrink-0 transition-[left] duration-300 ${
          sidebarCollapsed ? 'left-12' : 'left-64'
        }`}
      >
        <div className="flex items-center gap-4 min-w-0">
          <span className="font-semibold text-zinc-100 shrink-0">Kotte</span>
          <span className="text-zinc-500 text-sm truncate">
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
        <button
          type="button"
          onClick={handleDisconnect}
          className="shrink-0 px-3 py-1.5 text-sm rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
          aria-label="Disconnect from database"
        >
          Disconnect
        </button>
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
          <div className="shrink-0 px-3 py-2 bg-zinc-950 border-b border-zinc-800">
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
                onViewModeChange={(mode) => handleTabViewModeChange(activeTab.id, mode)}
                onNodeExpand={handleExpandNode}
                onNodeDelete={handleDeleteNode}
                onNodeSelect={(node) => setSelectedNode(node.id)}
                onEdgeSelect={(edge) => setSelectedEdge(edge.id)}
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
