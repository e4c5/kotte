import { useState } from 'react'
import GraphView, { type GraphNode, type GraphEdge } from './GraphView'
import TableView from './TableView'
import GraphControls from './GraphControls'
import NodeContextMenu from './NodeContextMenu'
import type { QueryTab } from '../stores/queryStore'

interface ResultTabProps {
  tab: QueryTab
  tablePageSize: number
  onViewModeChange: (mode: 'graph' | 'table') => void
  onNodeExpand: (nodeId: string) => Promise<void>
  onNodeDelete: (nodeId: string) => Promise<void>
  onExportReady: (exportFn: () => Promise<void>) => void
}

export default function ResultTab({
  tab,
  tablePageSize,
  onViewModeChange,
  onNodeExpand,
  onNodeDelete,
  onExportReady,
}: ResultTabProps) {
  const [showControls, setShowControls] = useState(false)
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, nodeId: string} | null>(null)
  const [exportGraph, setExportGraph] = useState<(() => Promise<void>) | null>(null)

  const result = tab.result
  if (!result) {
    // Hide "no results yet" when user has already run a query (error or loading)
    if (tab.error || tab.loading) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
          {tab.loading ? 'Executing query...' : 'Query failed. See the error message above.'}
        </div>
      )
    }
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
        No results yet. Execute a query to see results here.
      </div>
    )
  }

  const hasGraphData = !!(result.graph_elements?.nodes?.length || result.graph_elements?.edges?.length)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Results view: Graph View (visualization) | Table View (rows) - clearly visible tabs */}
      <div
        style={{
          padding: '0.5rem 1rem',
          borderBottom: '2px solid #dee2e6',
          display: 'flex',
          gap: '0.25rem',
          backgroundColor: '#e9ecef',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ marginRight: '0.75rem', fontWeight: 600, color: '#495057', fontSize: '0.9rem' }}>
          Results view:
        </span>
        <button
          onClick={() => onViewModeChange('graph')}
          disabled={!hasGraphData || !!result.visualization_warning}
          aria-label="Switch to graph view"
          aria-pressed={tab.viewMode === 'graph'}
          title={!hasGraphData ? 'Return nodes and/or edges in your query (e.g. RETURN n, r, m) to see the graph.' : undefined}
          style={{
            padding: '0.5rem 1rem',
            cursor: hasGraphData && !result.visualization_warning ? 'pointer' : 'not-allowed',
            border: '1px solid #adb5bd',
            borderBottom: tab.viewMode === 'graph' ? '2px solid transparent' : '1px solid #adb5bd',
            borderRadius: '6px 6px 0 0',
            marginBottom: tab.viewMode === 'graph' ? '-2px' : 0,
            backgroundColor: tab.viewMode === 'graph' ? '#fff' : 'transparent',
            color: tab.viewMode === 'graph' ? '#007bff' : (hasGraphData ? '#495057' : '#868e96'),
            fontWeight: tab.viewMode === 'graph' ? 600 : 500,
            opacity: hasGraphData && !result.visualization_warning ? 1 : 0.7,
          }}
        >
          Graph View
          {result.graph_elements && (
            <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', fontWeight: 400 }}>
              ({String(result.stats?.nodes_extracted || 0)} nodes, {String(result.stats?.edges_extracted || 0)} edges)
            </span>
          )}
        </button>
        <button
          onClick={() => onViewModeChange('table')}
          aria-label="Switch to table view"
          aria-pressed={tab.viewMode === 'table'}
          style={{
            padding: '0.5rem 1rem',
            cursor: 'pointer',
            border: '1px solid #adb5bd',
            borderBottom: tab.viewMode === 'table' ? '2px solid transparent' : '1px solid #adb5bd',
            borderRadius: '6px 6px 0 0',
            marginBottom: tab.viewMode === 'table' ? '-2px' : 0,
            backgroundColor: tab.viewMode === 'table' ? '#fff' : 'transparent',
            color: tab.viewMode === 'table' ? '#007bff' : '#495057',
            fontWeight: tab.viewMode === 'table' ? 600 : 500,
          }}
        >
          Table View ({result.row_count} rows)
        </button>
        
        {tab.viewMode === 'graph' && hasGraphData && (
          <>
            {exportGraph && (
              <button
                onClick={async () => {
                  try {
                    await exportGraph()
                  } catch (error) {
                    console.error('Failed to export graph:', error)
                    alert('Failed to export graph. Please try again.')
                  }
                }}
                style={{
                  marginLeft: 'auto',
                  padding: '0.5rem 1rem',
                  cursor: 'pointer',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  color: 'black',
                }}
                title="Export graph as PNG"
              >
                Export PNG
              </button>
            )}
            <button
              onClick={() => setShowControls(!showControls)}
              style={{
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
          </>
        )}
      </div>

      {/* Visualization warning */}
      {result.visualization_warning && (
        <div
          style={{
            padding: '0.75rem 1rem',
            backgroundColor: '#fff3cd',
            borderBottom: '1px solid #ffc107',
            color: '#856404',
          }}
        >
          <strong>Warning:</strong> {result.visualization_warning}
        </div>
      )}

      {/* Results content */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative' }}>
        {showControls && tab.viewMode === 'graph' && (
          <div
            style={{
              width: '300px',
              borderRight: '1px solid #ccc',
              overflow: 'auto',
              backgroundColor: 'white',
            }}
          >
            <GraphControls
              availableNodeLabels={Array.from(new Set(result.graph_elements?.nodes?.map(n => n.label) || []))}
              availableEdgeLabels={Array.from(new Set(result.graph_elements?.edges?.map(e => e.label) || []))}
            />
          </div>
        )}

        <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
          {tab.viewMode === 'graph' && hasGraphData ? (
            <>
              <GraphView
                nodes={result.graph_elements?.nodes as GraphNode[] || []}
                edges={result.graph_elements?.edges as GraphEdge[] || []}
                onNodeRightClick={(node, event) => {
                  setContextMenu({ nodeId: node.id, x: event.clientX, y: event.clientY })
                }}
                onExportReady={(exportFn) => {
                  setExportGraph(() => exportFn)
                  onExportReady(exportFn)
                }}
              />
              {contextMenu && (
                <NodeContextMenu
                  x={contextMenu.x}
                  y={contextMenu.y}
                  nodeId={contextMenu.nodeId}
                  onExpand={async () => {
                    await onNodeExpand(contextMenu.nodeId)
                    setContextMenu(null)
                  }}
                  onDelete={async () => {
                    await onNodeDelete(contextMenu.nodeId)
                    setContextMenu(null)
                  }}
                  onClose={() => setContextMenu(null)}
                />
              )}
            </>
          ) : (
            <TableView
              columns={result.columns}
              rows={result.rows}
              pageSize={tablePageSize}
            />
          )}
        </div>
      </div>
    </div>
  )
}

