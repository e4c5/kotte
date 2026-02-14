import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '../stores/sessionStore'
import { useQueryStore } from '../stores/queryStore'
import QueryEditor, { getQueryParams } from '../components/QueryEditor'
import GraphView, { type GraphNode, type GraphEdge } from '../components/GraphView'
import TableView from '../components/TableView'
import MetadataSidebar from '../components/MetadataSidebar'

type ViewMode = 'graph' | 'table'

export default function WorkspacePage() {
  const navigate = useNavigate()
  const { status, refreshStatus, disconnect } = useSessionStore()
  const {
    query,
    params,
    currentGraph,
    result,
    loading,
    error,
    setQuery,
    setParams,
    setCurrentGraph,
    executeQuery,
    clearResult,
    clearError,
    history,
  } = useQueryStore()

  const [viewMode, setViewMode] = useState<ViewMode>('graph')

  useEffect(() => {
    refreshStatus()
  }, [refreshStatus])

  useEffect(() => {
    if (status && !status.connected) {
      navigate('/')
    }
  }, [status, navigate])

  const handleDisconnect = async () => {
    await disconnect()
    navigate('/')
  }

  const handleExecute = async () => {
    if (!currentGraph || !query.trim()) {
      return
    }

    try {
      const queryParams = getQueryParams(params)
      await executeQuery(currentGraph, query, queryParams)
      
      // Auto-switch to graph view if graph elements are present
      if (result?.graph_elements) {
        const hasElements =
          (result.graph_elements.nodes?.length || 0) > 0 ||
          (result.graph_elements.edges?.length || 0) > 0
        if (hasElements) {
          setViewMode('graph')
        } else {
          setViewMode('table')
        }
      } else {
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

  const handleNodeClick = (node: GraphNode) => {
    console.log('Node clicked:', node)
    // TODO: Show node details or expand neighborhood
  }

  const handleNodeRightClick = (node: GraphNode, event: MouseEvent) => {
    event.preventDefault()
    console.log('Node right-clicked:', node)
    // TODO: Show context menu
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
                }}
              >
                <button
                  onClick={() => setViewMode('graph')}
                  disabled={!hasGraphData}
                  style={{
                    padding: '0.5rem 1rem',
                    cursor: hasGraphData ? 'pointer' : 'not-allowed',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    backgroundColor: viewMode === 'graph' ? '#007bff' : 'white',
                    color: viewMode === 'graph' ? 'white' : 'black',
                    opacity: hasGraphData ? 1 : 0.5,
                  }}
                >
                  Graph View
                  {result.stats?.nodes_extracted && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.85rem' }}>
                      ({result.stats.nodes_extracted} nodes, {result.stats.edges_extracted} edges)
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
              </div>

              {/* Result content */}
              <div style={{ flex: 1, minHeight: 0 }}>
                {viewMode === 'graph' && hasGraphData ? (
                  <GraphView
                    nodes={graphNodes}
                    edges={graphEdges}
                    width={window.innerWidth - 300}
                    height={window.innerHeight - 400}
                    onNodeClick={handleNodeClick}
                    onNodeRightClick={handleNodeRightClick}
                  />
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

