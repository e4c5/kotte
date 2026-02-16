import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'
import { useQueryStore } from '../stores/queryStore'
import { useGraphStore } from '../stores/graphStore'
import { useAuthStore } from '../stores/authStore'
import QueryEditor, { getQueryParams } from '../components/QueryEditor'
import GraphView, { type GraphNode, type GraphEdge } from '../components/GraphView'
import TableView from '../components/TableView'
import MetadataSidebar from '../components/MetadataSidebar'
import GraphControls from '../components/GraphControls'
import NodeContextMenu from '../components/NodeContextMenu'
import { graphAPI } from '../services/graph'

type ViewMode = 'graph' | 'table'

export default function WorkspacePage() {
  const navigate = useNavigate()
  const { status, refreshStatus, disconnect } = useSessionStore()
  const { authenticated, logout: authLogout, checkAuth } = useAuthStore()
  const {
    query,
    params,
    currentGraph,
    result,
    loading,
    error,
    setQuery,
    setCurrentGraph,
    executeQuery,
    cancelQuery,
    clearResult,
    clearError,
    history,
    mergeGraphElements,
  } = useQueryStore()

  const [viewMode, setViewMode] = useState<ViewMode>('graph')
  const [showControls, setShowControls] = useState(false)
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, nodeId: string} | null>(null)
  const [expanding, setExpanding] = useState(false)
  const { setSelectedNode } = useGraphStore()

  useEffect(() => {
    checkAuth().then(() => {
      if (!authenticated) {
        navigate('/login')
      } else {
        refreshStatus()
      }
    })
  }, [authenticated, navigate, checkAuth, refreshStatus])

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
    if (!currentGraph || !query.trim()) {
      return
    }

    try {
      const queryParams = getQueryParams(params)
      await executeQuery(currentGraph, query, queryParams)
      
      // Auto-switch view based on result and visualization limits
      if (result?.graph_elements && !result.visualization_warning) {
        const hasElements =
          (result.graph_elements.nodes?.length || 0) > 0 ||
          (result.graph_elements.edges?.length || 0) > 0
        if (hasElements) {
          setViewMode('graph')
        } else {
          setViewMode('table')
        }
      } else {
        // If there's a visualization warning, force table view
        setViewMode('table')
      }
    } catch (err) {
      // Error handled by store
    }
  }

  const handleGraphSelect = (graphName: string) => {
    setCurrentGraph(graphName)
    clearResult()
  }

  const handleQueryTemplate = (templateQuery: string) => {
    setQuery(templateQuery)
  }

  // Extract available labels from graph elements
  const availableLabels = useMemo(() => {
    if (!result?.graph_elements) {
      return { nodeLabels: [], edgeLabels: [] }
    }

    const nodeLabels = Array.from(
      new Set(result.graph_elements.nodes?.map((n) => n.label) || [])
    )
    const edgeLabels = Array.from(
      new Set(result.graph_elements.edges?.map((e) => e.label) || [])
    )

    return { nodeLabels, edgeLabels }
  }, [result])

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node.id)
    console.log('Node clicked:', node)
  }

  const handleNodeRightClick = (node: GraphNode, event: MouseEvent) => {
    event.preventDefault()
    setSelectedNode(node.id)
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      nodeId: node.id,
    })
  }

  const handleExpandNode = async (nodeId: string) => {
    if (!currentGraph || expanding) {
      return
    }

    setExpanding(true)
    try {
      const expandResult = await graphAPI.expandNode(currentGraph, nodeId, {
        depth: 1,
        limit: 100,
      })
      
      // Merge expanded nodes and edges into existing result
      mergeGraphElements(expandResult.nodes, expandResult.edges)
    } catch (err) {
      console.error('Failed to expand node:', err)
      // Could show error message to user
    } finally {
      setExpanding(false)
    }
  }

  if (!status || !status.connected) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>
    )
  }

  // Convert graph elements to GraphView format
  const graphNodes: GraphNode[] =
    result?.graph_elements?.nodes?.map((n) => ({
      id: n.id,
      label: n.label,
      properties: n.properties,
    })) || []

  const graphEdges: GraphEdge[] =
    result?.graph_elements?.edges?.map((e) => ({
      id: e.id,
      label: e.label,
      source: e.source,
      target: e.target,
      properties: e.properties,
    })) || []

  const hasGraphData = graphNodes.length > 0 || graphEdges.length > 0

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
              onCancel={cancelQuery}
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
                }}
              >
                <strong>Error:</strong> {error}
                <button
                  onClick={clearError}
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

          {/* Results */}
          {result && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              {/* View mode toggle */}
              <div
                style={{
                  padding: '0.5rem 1rem',
                  borderBottom: '1px solid #ccc',
                  display: 'flex',
                  gap: '0.5rem',
                  backgroundColor: '#f9f9f9',
                  alignItems: 'center',
                }}
              >
                <button
                  onClick={() => setViewMode('graph')}
                  disabled={!hasGraphData || !!result.visualization_warning}
                  style={{
                    padding: '0.5rem 1rem',
                    cursor: hasGraphData && !result.visualization_warning ? 'pointer' : 'not-allowed',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    backgroundColor: viewMode === 'graph' ? '#007bff' : 'white',
                    color: viewMode === 'graph' ? 'white' : 'black',
                    opacity: hasGraphData && !result.visualization_warning ? 1 : 0.5,
                  }}
                >
                  Graph View
                  {result.graph_elements && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.85rem' }}>
                      ({result.graph_elements.nodes?.length || 0} nodes, {result.graph_elements.edges?.length || 0} edges)
                    </span>
                  )}
                  {result.visualization_warning && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.85rem', color: '#dc3545' }}>
                      (Too large)
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setViewMode('table')}
                  style={{
                    padding: '0.5rem 1rem',
                    cursor: 'pointer',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    backgroundColor: viewMode === 'table' ? '#007bff' : 'white',
                    color: viewMode === 'table' ? 'white' : 'black',
                  }}
                >
                  Table View ({result.row_count} rows)
                </button>
                {viewMode === 'graph' && hasGraphData && (
                  <button
                    onClick={() => setShowControls(!showControls)}
                    style={{
                      marginLeft: 'auto',
                      padding: '0.5rem 1rem',
                      cursor: 'pointer',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                      backgroundColor: showControls ? '#007bff' : 'white',
                      color: showControls ? 'white' : 'black',
                    }}
                  >
                    {showControls ? 'Hide' : 'Show'} Controls
                  </button>
                )}
              </div>

              {/* Result content */}
              <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
                {viewMode === 'graph' && hasGraphData ? (
                  <>
                    <GraphView
                      nodes={graphNodes}
                      edges={graphEdges}
                      width={window.innerWidth - 300}
                      height={window.innerHeight - 400}
                      onNodeClick={handleNodeClick}
                      onNodeRightClick={handleNodeRightClick}
                    />
                    {showControls && (
                      <GraphControls
                        availableNodeLabels={availableLabels.nodeLabels}
                        availableEdgeLabels={availableLabels.edgeLabels}
                        onClose={() => setShowControls(false)}
                      />
                    )}
                    {contextMenu && (
                      <NodeContextMenu
                        x={contextMenu.x}
                        y={contextMenu.y}
                        nodeId={contextMenu.nodeId}
                        onExpand={handleExpandNode}
                        onClose={() => setContextMenu(null)}
                      />
                    )}
                    {expanding && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '10px',
                          right: '10px',
                          padding: '0.5rem 1rem',
                          backgroundColor: '#fff3cd',
                          border: '1px solid #ffc107',
                          borderRadius: '4px',
                          color: '#856404',
                          zIndex: 1001,
                        }}
                      >
                        Expanding neighborhood...
                      </div>
                    )}
                  </>
                ) : (
                  <TableView
                    columns={result.columns}
                    rows={result.rows}
                  />
                )}
              </div>
            </div>
          )}

          {!result && !loading && (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#999',
              }}
            >
              Execute a query to see results
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

