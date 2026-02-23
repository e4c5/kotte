import { useState, useMemo, useRef, useEffect } from 'react'
import GraphView, { type GraphNode, type GraphEdge, type PathHighlights } from './GraphView'
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
  onNodeSelect?: (node: GraphNode) => void
  onEdgeSelect?: (edge: GraphEdge) => void
  onExportReady: (exportFn: () => Promise<void>) => void
}

export default function ResultTab({
  tab,
  tablePageSize,
  onViewModeChange,
  onNodeExpand,
  onNodeDelete,
  onNodeSelect,
  onEdgeSelect,
  onExportReady,
}: ResultTabProps) {
  const [showControls, setShowControls] = useState(false)
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, nodeId: string} | null>(null)
  const [exportGraph, setExportGraph] = useState<(() => Promise<void>) | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 800, height: 600 })
  const graphContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = graphContainerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0]?.contentRect ?? { width: 800, height: 600 }
      setGraphSize({ width: Math.max(1, width), height: Math.max(1, height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [tab.viewMode])

  const result = tab.result

  const hasGraphData = !!(
    result?.graph_elements?.nodes?.length ||
    result?.graph_elements?.edges?.length
  )

  const pathHighlights = useMemo((): PathHighlights | undefined => {
    const paths = result?.graph_elements?.paths
    if (!paths?.length) return undefined
    const first = paths[0]
    return {
      nodeIds: (first?.node_ids ?? []).map(String),
      edgeIds: (first?.edge_ids ?? []).map(String),
    }
  }, [result?.graph_elements?.paths])

  if (!result) {
    if (tab.error || tab.loading) {
      return (
        <div className="h-full flex items-center justify-center text-zinc-500">
          {tab.loading ? 'Executing query...' : 'Query failed. See the error message above.'}
        </div>
      )
    }
    return (
      <div className="h-full flex items-center justify-center text-zinc-500">
        No results yet. Execute a query to see results here.
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* View mode bar: Graph | Table + Export / Controls when graph */}
      <div className="shrink-0 flex items-center gap-2 px-3 py-2 bg-zinc-800/80 border-b border-zinc-700 flex-wrap">
        <span className="text-zinc-400 text-sm font-medium mr-2">Results view:</span>
        <button
          type="button"
          onClick={() => onViewModeChange('graph')}
          disabled={!hasGraphData || !!result.visualization_warning}
          aria-label="Switch to graph view"
          aria-pressed={tab.viewMode === 'graph'}
          title={
            !hasGraphData
              ? 'Return nodes and/or edges in your query (e.g. RETURN n, r, m) to see the graph.'
              : result.visualization_warning ?? undefined
          }
          className={`px-3 py-1.5 rounded-t text-sm font-medium transition-colors ${
            tab.viewMode === 'graph'
              ? 'bg-zinc-700 text-blue-400'
              : hasGraphData && !result.visualization_warning
                ? 'text-zinc-400 hover:bg-zinc-700/50'
                : 'text-zinc-500 cursor-not-allowed opacity-70'
          }`}
        >
          Graph View
          {result.graph_elements && (
            <span className="ml-1.5 text-zinc-500 font-normal">
              ({String(result.stats?.nodes_extracted ?? 0)} nodes, {String(result.stats?.edges_extracted ?? 0)} edges)
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => onViewModeChange('table')}
          aria-label="Switch to table view"
          aria-pressed={tab.viewMode === 'table'}
          className={`px-3 py-1.5 rounded-t text-sm font-medium transition-colors ${
            tab.viewMode === 'table' ? 'bg-zinc-700 text-blue-400' : 'text-zinc-400 hover:bg-zinc-700/50'
          }`}
        >
          Table View ({result.row_count} rows)
        </button>
        {tab.viewMode === 'graph' && hasGraphData && (
          <>
            {exportGraph && (
              <button
                type="button"
                onClick={async () => {
                  try {
                    await exportGraph()
                  } catch (error) {
                    console.error('Failed to export graph:', error)
                    alert('Failed to export graph. Please try again.')
                  }
                }}
                className="ml-auto px-3 py-1.5 text-sm rounded border border-zinc-600 text-zinc-300 hover:bg-zinc-700"
                title="Export graph as PNG"
              >
                Export PNG
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowControls(!showControls)}
              className={`px-3 py-1.5 text-sm rounded border transition-colors ${
                showControls ? 'bg-blue-600 border-blue-500 text-white' : 'border-zinc-600 text-zinc-300 hover:bg-zinc-700'
              }`}
            >
              {showControls ? 'Hide' : 'Show'} Controls
            </button>
          </>
        )}
      </div>

      {result.visualization_warning && (
        <div className="shrink-0 px-3 py-2 bg-amber-900/30 border-b border-amber-700/50 text-amber-200 text-sm">
          <strong>Warning:</strong> {result.visualization_warning}
        </div>
      )}

      <div className="flex-1 flex min-h-0 relative">
        {showControls && tab.viewMode === 'graph' && (
          <div className="w-72 shrink-0 border-r border-zinc-700 overflow-auto bg-zinc-800/50">
            <GraphControls
              availableNodeLabels={Array.from(new Set(result.graph_elements?.nodes?.map(n => n.label) || []))}
              availableEdgeLabels={Array.from(new Set(result.graph_elements?.edges?.map(e => e.label) || []))}
            />
          </div>
        )}

        <div ref={graphContainerRef} className="flex-1 relative min-w-0 min-h-0">
          {tab.viewMode === 'graph' && hasGraphData ? (
            <>
              <GraphView
                width={graphSize.width}
                height={graphSize.height}
                nodes={result.graph_elements?.nodes as GraphNode[] || []}
                edges={result.graph_elements?.edges as GraphEdge[] || []}
                pathHighlights={pathHighlights}
                onNodeClick={onNodeSelect}
                onNodeRightClick={(node, event) => {
                  setContextMenu({ nodeId: node.id, x: event.clientX, y: event.clientY })
                }}
                onEdgeClick={onEdgeSelect}
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
              queriedGraph={tab.graph}
            />
          )}
        </div>
      </div>
    </div>
  )
}

