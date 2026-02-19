import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'
import { useQueryStore } from '../stores/queryStore'
import { useGraphStore } from '../stores/graphStore'
import { useAuthStore } from '../stores/authStore'
import { useSettingsStore } from '../stores/settingsStore'
import QueryEditor, { getQueryParams } from '../components/QueryEditor'
import MetadataSidebar from '../components/MetadataSidebar'
import SettingsModal from '../components/SettingsModal'
import TabBar from '../components/TabBar'
import ResultTab from '../components/ResultTab'
import { graphAPI } from '../services/graph'

export default function WorkspacePage() {
  const navigate = useNavigate()
  const { status, refreshStatus, disconnect } = useSessionStore()
  const { logout: authLogout, checkAuth } = useAuthStore()
  const {
    tabs,
    activeTabId,
    query,
    params,
    currentGraph,
    loading,
    error,
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
  } = useQueryStore()

  const {
    tablePageSize,
    defaultLayout,
  } = useSettingsStore()
  
  const [showSettings, setShowSettings] = useState(false)
  const [expanding, setExpanding] = useState(false)
  const { setSelectedNode, layout, setLayout } = useGraphStore()
  
  // Initialize with a default tab if none exists
  useEffect(() => {
    if (tabs.length === 0) {
      createTab('Query 1')
    } else if (!activeTabId) {
      setActiveTab(tabs[0].id)
    }
  }, []) // Only run on mount
  
  // Apply default layout from settings on mount
  useEffect(() => {
    if (defaultLayout && layout !== defaultLayout) {
      setLayout(defaultLayout)
    }
  }, [defaultLayout, layout, setLayout])

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
      await executeQuery(activeTabId, currentGraph, query, queryParams)
      
      // Auto-switch view based on result and visualization limits
      const tab = tabs.find(t => t.id === activeTabId)
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
      // Don't close the last tab, just clear it
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
    if (!activeTabId || !currentGraph || expanding) {
      return
    }

    setExpanding(true)
    try {
      const expandResult = await graphAPI.expandNode(currentGraph, nodeId, {
        depth: 1,
        limit: 100,
      })
      
      // Merge expanded nodes and edges into existing result
      mergeGraphElements(activeTabId, expandResult.nodes, expandResult.edges)
    } catch (err) {
      console.error('Failed to expand node:', err)
    } finally {
      setExpanding(false)
    }
  }

  const handleDeleteNode = async (nodeId: string) => {
    if (!activeTabId || !currentGraph) {
      return
    }

    // Show confirmation dialog
    const confirmMessage = 
      'Are you sure you want to delete this node?\n\n' +
      'This will delete the node and all its relationships.\n' +
      'This action cannot be undone.'
    
    if (!confirm(confirmMessage)) {
      return
    }

    try {
      // Delete the node with detach=true to remove relationships
      await graphAPI.deleteNode(currentGraph, nodeId, { detach: true })
      
      // Remove the node from the current result
      const tab = tabs.find(t => t.id === activeTabId)
      if (tab?.result?.graph_elements) {
        // Remove node from nodes array
        const updatedNodes = tab.result.graph_elements.nodes?.filter((n) => n.id !== nodeId) || []
        
        // Remove edges connected to this node
        const updatedEdges = tab.result.graph_elements.edges?.filter(
          (e) => e.source !== nodeId && e.target !== nodeId
        ) || []
        
        // Update result in the store
        updateResult(activeTabId, (currentResult) => {
          if (!currentResult) return null
          return {
            ...currentResult,
            graph_elements: {
              nodes: updatedNodes,
              edges: updatedEdges,
            },
          }
        })
        
        console.log(`Node ${nodeId} deleted successfully`)
      }
      
      // Clear selection
      setSelectedNode(null)
    } catch (err) {
      console.error('Failed to delete node:', err)
      alert('Failed to delete node. Please try again.')
    }
  }
  
  const handleTabViewModeChange = (tabId: string, mode: 'graph' | 'table') => {
    updateTab(tabId, { viewMode: mode })
  }
  
  const handleTabExportReady = (_tabId: string, _exportFn: () => Promise<void>) => {
    // Store export function for the tab if needed
  }

  if (!status || !status.connected) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>
    )
  }

  const activeTab = tabs.find(t => t.id === activeTabId)

  return (
    <div style={{ display: 'flex', height: '100vh', flexDirection: 'column' }}>
      {/* Header */}
      <div
        style={{
          padding: '1rem',
          borderBottom: '1px solid #ccc',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#f5f5f5',
        }}
      >
        <div>
          <strong>Kotte</strong> - Connected to {status.database} on{' '}
          {status.host}:{status.port}
        </div>
        <button
          onClick={handleDisconnect}
          aria-label="Disconnect from database"
          style={{
            padding: '0.5rem 1rem',
            cursor: 'pointer',
            border: '1px solid #ccc',
            borderRadius: '4px',
            backgroundColor: 'white',
          }}
        >
          Disconnect
        </button>
      </div>

      {/* Main content */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Metadata Sidebar */}
        <MetadataSidebar
          currentGraph={currentGraph || undefined}
          onGraphSelect={handleGraphSelect}
          onQueryTemplate={handleQueryTemplate}
        />

        {/* Editor and Results */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* Tab Bar */}
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

          {/* Query Editor */}
          <div
            style={{
              borderBottom: '1px solid #ccc',
              padding: '1rem',
              minHeight: '300px',
              maxHeight: '400px',
            }}
          >
            <QueryEditor
              value={query}
              onChange={setQuery}
              onExecute={handleExecute}
              onCancel={() => activeTabId && cancelQuery(activeTabId)}
              loading={loading}
              history={history}
            />
            {error && (
              <div
                style={{
                  marginTop: '1rem',
                  padding: '0.75rem',
                  backgroundColor: '#fee',
                  border: '1px solid #fcc',
                  borderRadius: '4px',
                  color: '#c00',
                  userSelect: 'text',
                  cursor: 'text',
                }}
              >
                <strong>Error:</strong> <span style={{ userSelect: 'text' }}>{error}</span>
                <button
                  onClick={() => activeTabId && clearError(activeTabId)}
                  style={{
                    float: 'right',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                  }}
                >
                  ×
                </button>
              </div>
            )}
            {loading && (
              <div style={{ marginTop: '1rem', padding: '0.75rem' }}>
                Executing query...
              </div>
            )}
          </div>

          {/* Results - Show active tab's result */}
          {activeTab && (
            <ResultTab
              tab={activeTab}
              tablePageSize={tablePageSize}
              onViewModeChange={(mode) => handleTabViewModeChange(activeTab.id, mode)}
              onNodeExpand={handleExpandNode}
              onNodeDelete={handleDeleteNode}
              onExportReady={(exportFn) => handleTabExportReady(activeTab.id, exportFn)}
            />
          )}

          {!activeTab && (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#999',
              }}
            >
              No active tab. Create a new tab to start querying.
            </div>
          )}
        </div>
      </div>
      {showSettings && (
        <SettingsModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  )
}

