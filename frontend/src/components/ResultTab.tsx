import { useState, useMemo, useRef, useLayoutEffect } from 'react'
import GraphView, { type GraphNode, type GraphEdge, type PathHighlights } from './GraphView'
import TableView from './TableView'
import GraphControls from './GraphControls'
import NodeContextMenu from './NodeContextMenu'
import type { QueryTab } from '../stores/queryStore'
import { useGraphStore } from '../stores/graphStore'

interface ResultTabProps {
  tab: QueryTab
  tablePageSize: number
  /**
   * Client-side reason the graph view is unavailable for this result
   * (e.g. result exceeds `maxNodesForGraph` / `maxEdgesForGraph` from
   * `settingsStore`). Merges with `result.visualization_warning` from the
   * server: either source disables the Graph button and shows a banner.
   */
  vizDisabledReason?: string | null
  onOpenSettings?: () => void
  onViewModeChange: (mode: 'graph' | 'table') => void
  onNodeExpand: (nodeId: string) => Promise<void>
  onNodeDelete: (nodeId: string) => Promise<void>
  onNodeSelect?: (node: GraphNode) => void
  onNodeDoubleClick?: (node: GraphNode) => void
  onEdgeSelect?: (edge: GraphEdge) => void
  onExportReady: (exportFn: () => Promise<void>) => void
}

export default function ResultTab({
  tab,
  tablePageSize,
  vizDisabledReason = null,
  onOpenSettings,
  onViewModeChange,
  onNodeExpand,
  onNodeDelete,
  onNodeSelect,
  onNodeDoubleClick,
  onEdgeSelect,
  onExportReady,
}: ResultTabProps) {
  const [showControls, setShowControls] = useState(false)
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, nodeId: string} | null>(null)
  // ROADMAP A3: Pin/Hide actions exposed via NodeContextMenu. The store
  // already had `togglePinNode`/`toggleHideNode` and the simulation already
  // honoured `pinnedNodes`; the menu was the missing UI surface.
  const pinnedNodes = useGraphStore((s) => s.pinnedNodes)
  const hiddenNodes = useGraphStore((s) => s.hiddenNodes)
  const togglePinNode = useGraphStore((s) => s.togglePinNode)
  const toggleHideNode = useGraphStore((s) => s.toggleHideNode)
  const [exportGraph, setExportGraph] = useState<(() => Promise<void>) | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 800, height: 600 })
  const graphContainerRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const el = graphContainerRef.current
    if (!el) return
    const MIN_WIDTH = 400
    const MIN_HEIGHT = 300
    const applySize = (w: number, h: number) => {
      if (w > 0 && h > 0) {
        setGraphSize({
          width: Math.max(MIN_WIDTH, w),
          height: Math.max(MIN_HEIGHT, h),
        })
      }
    }
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0]?.contentRect ?? { width: 0, height: 0 }
      applySize(width, height)
    })
    ro.observe(el)
    // Initial size after layout (ResizeObserver can fire with 0 before layout completes)
    const raf = requestAnimationFrame(() => {
      const rect = el.getBoundingClientRect()
      applySize(rect.width, rect.height)
    })
    const onWindowResize = () => {
      const rect = el.getBoundingClientRect()
      applySize(rect.width, rect.height)
    }
    window.addEventListener('resize', onWindowResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onWindowResize)
      ro.disconnect()
    }
  }, [tab.viewMode, showControls])

  const result = tab.result

  const hasGraphData = !!(
    result?.graph_elements?.nodes?.length ||
    result?.graph_elements?.edges?.length
  )

  // Single source of truth for "graph view is unavailable for this result".
  // `result.visualization_warning` comes from the server (e.g. the backend
  // truncated the result); `vizDisabledReason` comes from WorkspacePage's
  // client-side check against `maxNodesForGraph` / `maxEdgesForGraph`. Either
  // disables the Graph button and surfaces a banner above the canvas.
  const vizUnavailableReason: string | null =
    result?.visualization_warning ?? vizDisabledReason

  const pathHighlights = useMemo((): PathHighlights | undefined => {
    const paths = result?.graph_elements?.paths
    if (!paths?.length) return undefined
    const first = paths[0]
    return {
      nodeIds: (first?.node_ids ?? []).map(String),
      edgeIds: (first?.edge_ids ?? []).map(String),
    }
  }, [result?.graph_elements?.paths])

  const availableNodeLabels = useMemo(
    () => Array.from(new Set(result?.graph_elements?.nodes?.map(n => n.label) || [])),
    [result?.graph_elements?.nodes]
  )

  const availableEdgeLabels = useMemo(
    () => Array.from(new Set(result?.graph_elements?.edges?.map(e => e.label) || [])),
    [result?.graph_elements?.edges]
  )

  const closeContextMenu = () => setContextMenu(null)

  const handleExportGraph = async () => {
    if (!exportGraph) return
    try {
      await exportGraph()
    } catch (error) {
      console.error('Failed to export graph:', error)
      alert('Failed to export graph. Please try again.')
    }
  }

  const handleNodeExpand = async () => {
    if (!contextMenu) return
    try {
      await onNodeExpand(contextMenu.nodeId)
    } finally {
      closeContextMenu()
    }
  }

  const handleNodeDelete = async () => {
    if (!contextMenu) return
    try {
      await onNodeDelete(contextMenu.nodeId)
    } finally {
      closeContextMenu()
    }
  }

  const handleNodePin = (nodeId: string) => {
    togglePinNode(nodeId)
  }

  const handleNodeHide = (nodeId: string) => {
    toggleHideNode(nodeId)
  }

  const handleNodeContextMenu = (node: GraphNode, event: MouseEvent) => {
    setContextMenu({ nodeId: node.id, x: event.clientX, y: event.clientY })
  }

  const handleExportReady = (exportFn: () => Promise<void>) => {
    setExportGraph(() => exportFn)
    onExportReady(exportFn)
  }

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

  let graphTabStateClasses: string
  if (tab.viewMode === 'graph') {
    graphTabStateClasses = 'bg-zinc-700 text-blue-400'
  } else if (hasGraphData && !vizUnavailableReason) {
    graphTabStateClasses = 'text-zinc-400 hover:bg-zinc-700/50'
  } else {
    graphTabStateClasses = 'text-zinc-500 cursor-not-allowed opacity-70'
  }

  let graphTabTitle: string | undefined
  if (!hasGraphData) {
    graphTabTitle =
      'Return nodes and/or edges in your query (e.g. RETURN n, r, m) to see the graph.'
  } else {
    graphTabTitle = vizUnavailableReason ?? undefined
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* View mode bar: Graph | Table + Export / Controls when graph */}
      <div className="shrink-0 flex items-center gap-2 px-3 py-2 bg-zinc-800/80 border-b border-zinc-700 flex-wrap">
        <span className="text-zinc-400 text-sm font-medium mr-2">Results view:</span>
        <button
          type="button"
          onClick={() => onViewModeChange('graph')}
          disabled={!hasGraphData || !!vizUnavailableReason}
          aria-label="Switch to graph view"
          aria-pressed={tab.viewMode === 'graph'}
          title={graphTabTitle}
          className={`px-3 py-1.5 rounded-t text-sm font-medium transition-colors ${graphTabStateClasses}`}
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
                onClick={handleExportGraph}
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

      {vizUnavailableReason && (
        <output
          data-testid="viz-unavailable-banner"
          className="shrink-0 px-3 py-2 bg-amber-900/30 border-b border-amber-700/50 text-amber-200 text-sm flex flex-wrap items-center gap-3"
        >
          <span className="flex-1">
            <strong>Visualization unavailable:</strong> {vizUnavailableReason}
          </span>
          {vizDisabledReason && onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="shrink-0 px-2 py-1 rounded border border-amber-500/60 text-amber-100 hover:bg-amber-800/40 text-xs font-medium"
            >
              Open Settings
            </button>
          )}
        </output>
      )}

      <div className="flex-1 flex min-h-0 relative">
        <div ref={graphContainerRef} className="flex-1 relative min-w-0 min-h-0 flex flex-col overflow-hidden">
          {tab.viewMode === 'graph' && hasGraphData ? (
            <>
              <GraphView
                width={graphSize.width}
                height={graphSize.height}
                nodes={result.graph_elements?.nodes as GraphNode[] || []}
                edges={result.graph_elements?.edges as GraphEdge[] || []}
                pathHighlights={pathHighlights}
                onNodeClick={onNodeSelect}
                onNodeDoubleClick={onNodeDoubleClick}
                onNodeRightClick={handleNodeContextMenu}
                onEdgeClick={onEdgeSelect}
                onExportReady={handleExportReady}
              />
              {contextMenu && (
                <NodeContextMenu
                  x={contextMenu.x}
                  y={contextMenu.y}
                  nodeId={contextMenu.nodeId}
                  onExpand={handleNodeExpand}
                  onDelete={handleNodeDelete}
                  onPin={handleNodePin}
                  onHide={handleNodeHide}
                  isPinned={pinnedNodes.has(contextMenu.nodeId)}
                  isHidden={hiddenNodes.has(contextMenu.nodeId)}
                  onClose={closeContextMenu}
                />
              )}
              {showControls && (
                <GraphControls
                  availableNodeLabels={availableNodeLabels}
                  availableEdgeLabels={availableEdgeLabels}
                  onClose={() => setShowControls(false)}
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
