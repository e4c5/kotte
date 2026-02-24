import { useEffect, useState } from 'react'
import { graphAPI, type GraphInfo, type GraphMetadata } from '../services/graph'
import { getNodeLabelColor } from '../utils/nodeColors'

interface MetadataSidebarProps {
  currentGraph?: string
  onGraphSelect: (graphName: string) => void
  onQueryTemplate: (query: string) => void
  /** Controlled: whether the sidebar is collapsed. Parent is the source of truth. */
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

export default function MetadataSidebar({
  currentGraph,
  onGraphSelect,
  onQueryTemplate,
  collapsed,
  onCollapsedChange,
}: MetadataSidebarProps) {
  const [graphs, setGraphs] = useState<GraphInfo[]>([])
  const [metadata, setMetadata] = useState<GraphMetadata | null>(null)
  const [loading, setLoading] = useState(false)
  const [nodeLabelsOpen, setNodeLabelsOpen] = useState(true)
  const [edgeLabelsOpen, setEdgeLabelsOpen] = useState(true)

  useEffect(() => {
    loadGraphs()
  }, [])

  useEffect(() => {
    if (currentGraph) {
      loadMetadata(currentGraph)
    } else {
      setMetadata(null)
    }
  }, [currentGraph])

  const loadGraphs = async () => {
    try {
      const graphList = await graphAPI.listGraphs()
      setGraphs(graphList)
      if (graphList.length > 0 && !currentGraph) {
        onGraphSelect(graphList[0].name)
      }
    } catch (error) {
      console.error('Failed to load graphs:', error)
    }
  }

  const loadMetadata = async (graphName: string) => {
    setLoading(true)
    try {
      const meta = await graphAPI.getMetadata(graphName)
      setMetadata(meta)
    } catch (error) {
      console.error('Failed to load metadata:', error)
    } finally {
      setLoading(false)
    }
  }

  const generateQuery = (type: 'node' | 'edge', label: string) => {
    if (type === 'node') {
      return `MATCH (n:${label}) RETURN n LIMIT 100`
    }
    return `MATCH (a)-[r:${label}]->(b) RETURN a, r, b LIMIT 100`
  }

  if (collapsed) {
    return (
      <div className="fixed left-0 top-0 h-full w-12 bg-zinc-800 border-r border-zinc-700 flex flex-col items-center py-4 z-30 transition-all duration-300">
        <button
          type="button"
          onClick={() => onCollapsedChange(false)}
          className="p-2 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700"
          aria-label="Expand schema sidebar"
        >
          <span className="text-lg">›</span>
        </button>
      </div>
    )
  }

  return (
    <div className="fixed left-0 top-0 h-full w-64 bg-zinc-800 border-r border-zinc-700 shadow-lg flex flex-col z-30 transition-all duration-300 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-700 shrink-0">
        <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Schema</span>
        <button
          type="button"
          onClick={() => onCollapsedChange(true)}
          className="p-1.5 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700"
          aria-label="Collapse sidebar"
        >
          <span className="text-sm">‹</span>
        </button>
      </div>

      <div className="px-3 py-2 border-b border-zinc-700">
        <label htmlFor="graph-select" className="sr-only">Select graph</label>
        <select
          id="graph-select"
          value={currentGraph ?? ''}
          onChange={(e) => onGraphSelect(e.target.value)}
          className="w-full px-3 py-2 text-sm bg-zinc-700/50 border border-zinc-600 rounded-lg text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select a graph...</option>
          {graphs.map((g) => (
            <option key={g.name} value={g.name}>
              {g.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-auto py-2">
        {loading && (
          <div className="px-3 py-4 text-center text-sm text-zinc-500">Loading...</div>
        )}

        {metadata && !loading && (
          <div className="space-y-1">
            {/* Node Labels accordion */}
            <button
              type="button"
              onClick={() => setNodeLabelsOpen(!nodeLabelsOpen)}
              className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-semibold text-zinc-300 hover:bg-zinc-700/50 transition-colors"
              aria-expanded={nodeLabelsOpen}
            >
              Node Labels
              <span className="text-zinc-500 text-[10px]">{nodeLabelsOpen ? '▲' : '▼'}</span>
            </button>
            {nodeLabelsOpen && (
              <div className="flex flex-wrap gap-1.5 px-2 pb-3">
                {metadata.node_labels.map((label) => (
                  <button
                    key={label.label}
                    type="button"
                    onClick={() => onQueryTemplate(generateQuery('node', label.label))}
                    className="rounded-full px-3 py-1 text-xs font-semibold text-white transition-opacity hover:opacity-90"
                    style={{ backgroundColor: getNodeLabelColor(label.label) }}
                    title={`${label.label}${label.count > 0 ? ` (${label.count.toLocaleString()} nodes)` : ''} — Click to generate query`}
                  >
                    {label.label || '(no label)'}
                  </button>
                ))}
              </div>
            )}

            {/* Edge Labels accordion */}
            <button
              type="button"
              onClick={() => setEdgeLabelsOpen(!edgeLabelsOpen)}
              className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-semibold text-zinc-300 hover:bg-zinc-700/50 transition-colors"
              aria-expanded={edgeLabelsOpen}
            >
              Edge Labels
              <span className="text-zinc-500 text-[10px]">{edgeLabelsOpen ? '▲' : '▼'}</span>
            </button>
            {edgeLabelsOpen && (
              <div className="flex flex-wrap gap-1.5 px-2 pb-3">
                {metadata.edge_labels.map((label) => (
                  <button
                    key={label.label}
                    type="button"
                    onClick={() => onQueryTemplate(generateQuery('edge', label.label))}
                    className="rounded px-2.5 py-1 text-xs font-medium text-zinc-200 bg-zinc-700 hover:bg-zinc-600 transition-colors"
                    title={`${label.label}${label.count > 0 ? ` (${label.count.toLocaleString()} edges)` : ''} — Click to generate query`}
                  >
                    [{label.label || '(no label)'}]
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
