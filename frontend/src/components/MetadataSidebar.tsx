import { useCallback, useEffect, useRef, useState } from 'react'
import { graphAPI, type GraphInfo, type NodeLabel, type EdgeLabel } from '../services/graph'
import { queryAPI, type QueryTemplate } from '../services/query'
import { useGraphStore } from '../stores/graphStore'
import { getNodeLabelColor } from '../utils/nodeColors'

interface MetadataSidebarProps {
  currentGraph?: string
  onGraphSelect: (graphName: string) => void
  /** Second arg carries the template's default params JSON when invoked from the Library. */
  onQueryTemplate: (query: string, params?: string) => void
  /** Controlled: whether the sidebar is collapsed. Parent is the source of truth. */
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

// ---- LabelPropertiesPanel (shared by NodeLabelRow and EdgeLabelRow) ----------

interface LabelPropertiesPanelProps {
  readonly properties: string[]
  readonly property_types?: Record<string, string>
  readonly indexed_properties?: string[]
  readonly property_statistics?: Array<{ property: string; min?: unknown; max?: unknown }>
  readonly sampleQuery: string
  readonly matchAllQuery: string
  readonly sampleTitle: string
  readonly matchAllTitle: string
  readonly onQueryTemplate: (q: string) => void
}

function LabelPropertiesPanel({
  properties,
  property_types,
  indexed_properties,
  property_statistics,
  sampleQuery,
  matchAllQuery,
  sampleTitle,
  matchAllTitle,
  onQueryTemplate,
}: LabelPropertiesPanelProps) {
  return (
    <div className="mx-3 mb-2 rounded-md bg-zinc-900/60 border border-zinc-700/60 text-xs">
      {properties.length > 0 ? (
        <div className="px-2 pt-2 pb-1 flex flex-wrap gap-1">
          {properties.map((p) => (
            <span
              key={p}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-300 font-mono"
            >
              {p}
              {property_types?.[p] && (
                <span className="text-zinc-500 font-sans text-[10px]">{property_types[p]}</span>
              )}
              {indexed_properties?.includes(p) && (
                <span
                  className="text-[9px] px-0.5 rounded bg-amber-900/60 text-amber-400 font-sans leading-none"
                  title="Indexed"
                >
                  idx
                </span>
              )}
            </span>
          ))}
        </div>
      ) : (
        <p className="px-2 pt-2 pb-1 text-zinc-500 italic">No properties</p>
      )}
      {property_statistics && property_statistics.length > 0 && (
        <div className="px-2 pb-1 flex flex-col gap-0.5">
          {property_statistics.map((s) => (
            <span key={s.property} className="text-zinc-500">
              <span className="font-mono text-zinc-400">{s.property}</span>:{' '}
              {String(s.min ?? '?')} – {String(s.max ?? '?')}
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-1 px-2 pb-2 pt-1 border-t border-zinc-700/60">
        <button
          type="button"
          onClick={() => onQueryTemplate(sampleQuery)}
          className="flex-1 rounded border border-zinc-600 bg-zinc-800 px-2 py-1 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
          title={sampleTitle}
        >
          Sample 5
        </button>
        <button
          type="button"
          onClick={() => onQueryTemplate(matchAllQuery)}
          className="flex-1 rounded border border-zinc-600 bg-zinc-800 px-2 py-1 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
          title={matchAllTitle}
        >
          Match all
        </button>
      </div>
    </div>
  )
}

// ---- NodeLabelRow ------------------------------------------------------------

interface NodeLabelRowProps {
  readonly label: NodeLabel
  readonly onQueryTemplate: (q: string) => void
}

function NodeLabelRow({ label, onQueryTemplate }: NodeLabelRowProps) {
  const [open, setOpen] = useState(false)
  const color = getNodeLabelColor(label.label)

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-zinc-700/50 transition-colors group"
        aria-expanded={open}
      >
        <span
          className="shrink-0 w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: color }}
          aria-hidden="true"
        />
        <span className="flex-1 text-sm text-zinc-200 truncate">{label.label || '(no label)'}</span>
        {label.count > 0 && (
          <span className="shrink-0 text-[10px] text-zinc-500 tabular-nums">
            {label.count.toLocaleString()}
          </span>
        )}
        <span className="shrink-0 text-[10px] text-zinc-500 group-hover:text-zinc-400">
          {open ? '▲' : '▼'}
        </span>
      </button>
      {open && (
        <LabelPropertiesPanel
          properties={label.properties}
          property_types={label.property_types}
          indexed_properties={label.indexed_properties}
          sampleQuery={`MATCH (n:${label.label}) RETURN n LIMIT 5`}
          matchAllQuery={`MATCH (n:${label.label}) RETURN n LIMIT 100`}
          sampleTitle="Sample 5 nodes with this label"
          matchAllTitle="Generate MATCH query for all nodes with this label"
          onQueryTemplate={onQueryTemplate}
        />
      )}
    </div>
  )
}

// ---- EdgeLabelRow ------------------------------------------------------------

interface EdgeLabelRowProps {
  readonly label: EdgeLabel
  readonly onQueryTemplate: (q: string) => void
}

function EdgeLabelRow({ label, onQueryTemplate }: EdgeLabelRowProps) {
  const [open, setOpen] = useState(false)

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-zinc-700/50 transition-colors group"
        aria-expanded={open}
      >
        <span className="shrink-0 text-zinc-500 text-[10px]" aria-hidden="true">─▶</span>
        <span className="flex-1 text-sm text-zinc-300 truncate">{label.label || '(no label)'}</span>
        {label.count > 0 && (
          <span className="shrink-0 text-[10px] text-zinc-500 tabular-nums">
            {label.count.toLocaleString()}
          </span>
        )}
        <span className="shrink-0 text-[10px] text-zinc-500 group-hover:text-zinc-400">
          {open ? '▲' : '▼'}
        </span>
      </button>
      {open && (
        <LabelPropertiesPanel
          properties={label.properties}
          property_types={label.property_types}
          indexed_properties={label.indexed_properties}
          property_statistics={label.property_statistics}
          sampleQuery={`MATCH (a)-[r:${label.label}]->(b) RETURN a, r, b LIMIT 5`}
          matchAllQuery={`MATCH (a)-[r:${label.label}]->(b) RETURN a, r, b LIMIT 100`}
          sampleTitle="Sample 5 edges with this label"
          matchAllTitle="Generate MATCH query for all edges with this label"
          onQueryTemplate={onQueryTemplate}
        />
      )}
    </div>
  )
}

// ---- LibraryPanel -----------------------------------------------------------

interface LibraryPanelProps {
  onQueryTemplate: (query: string, params?: string) => void
}

function LibraryPanel({ onQueryTemplate }: LibraryPanelProps) {
  const [templates, setTemplates] = useState<QueryTemplate[]>([])
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    queryAPI.listTemplates().then(setTemplates).catch((err) => {
      console.error('Failed to load query templates:', err)
    })
  }, [])

  if (templates.length === 0) return null

  const handleUse = (t: QueryTemplate) => {
    const paramsJson = Object.keys(t.params).length > 0 ? JSON.stringify(t.params, null, 2) : undefined
    onQueryTemplate(t.cypher, paramsJson)
  }

  return (
    <div>
      <div className="border-t border-zinc-700/60" />
      <p className="px-3 pt-2 pb-1 text-xs font-semibold text-zinc-400 uppercase tracking-wide">
        Library
      </p>
      <div className="mb-1">
        {templates.map((t) => (
          <div key={t.id}>
            <button
              type="button"
              onClick={() => setOpen(open === t.id ? null : t.id)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-zinc-700/50 transition-colors group"
              aria-expanded={open === t.id}
            >
              <span className="flex-1 text-sm text-zinc-200 truncate">{t.name}</span>
              <span className="shrink-0 text-[10px] text-zinc-500 group-hover:text-zinc-400">
                {open === t.id ? '▲' : '▼'}
              </span>
            </button>
            {open === t.id && (
              <div className="mx-3 mb-2 rounded-md bg-zinc-900/60 border border-zinc-700/60 text-xs">
                <p className="px-2 pt-2 pb-1 text-zinc-400">{t.description}</p>
                {Object.keys(t.param_schema).length > 0 && (
                  <div className="px-2 pb-1 flex flex-wrap gap-1">
                    {Object.entries(t.param_schema).map(([key, schema]) => (
                      <span
                        key={key}
                        className="px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-300 font-mono"
                        title={schema.description}
                      >
                        ${key}
                        {schema.default !== undefined ? `=${String(schema.default)}` : ''}
                      </span>
                    ))}
                  </div>
                )}
                <div className="px-2 pb-2 pt-1 border-t border-zinc-700/60">
                  <button
                    type="button"
                    onClick={() => handleUse(t)}
                    className="w-full rounded border border-zinc-600 bg-zinc-800 px-2 py-1 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
                  >
                    Use template
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- MetadataSidebar --------------------------------------------------------

export default function MetadataSidebar({
  currentGraph,
  onGraphSelect,
  onQueryTemplate,
  collapsed,
  onCollapsedChange,
}: MetadataSidebarProps) {
  const [graphs, setGraphs] = useState<GraphInfo[]>([])
  const metadata = useGraphStore((s) => s.graphMetadata)
  const setGraphMetadata = useGraphStore((s) => s.setGraphMetadata)
  const metadataRequestSeq = useRef(0)
  const [loading, setLoading] = useState(false)
  const [nodeLabelsOpen, setNodeLabelsOpen] = useState(true)
  const [edgeLabelsOpen, setEdgeLabelsOpen] = useState(true)

  useEffect(() => {
    loadGraphs()
    // Mount-only fetch — `loadGraphs` is a stable closure; re-running on every
    // change would re-issue the request unnecessarily.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadMetadata = useCallback(
    async (graphName: string) => {
      const requestId = ++metadataRequestSeq.current
      setLoading(true)
      setGraphMetadata(null)
      try {
        const meta = await graphAPI.getMetadata(graphName)
        if (metadataRequestSeq.current !== requestId) {
          return
        }
        setGraphMetadata(meta)
      } catch (error) {
        if (metadataRequestSeq.current !== requestId) {
          return
        }
        console.error('Failed to load metadata:', error)
        setGraphMetadata(null)
      } finally {
        if (metadataRequestSeq.current === requestId) {
          setLoading(false)
        }
      }
    },
    [setGraphMetadata]
  )

  useEffect(() => {
    if (currentGraph) {
      loadMetadata(currentGraph).catch(() => {
        // Rejection is logged inside loadMetadata; avoid unhandled-rejection
      })
    } else {
      metadataRequestSeq.current += 1
      setLoading(false)
      setGraphMetadata(null)
    }
  }, [currentGraph, loadMetadata, setGraphMetadata])

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
          <div>
            {/* Node Labels section */}
            <button
              type="button"
              onClick={() => setNodeLabelsOpen(!nodeLabelsOpen)}
              className="w-full flex items-center justify-between px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wide hover:bg-zinc-700/50 transition-colors"
              aria-expanded={nodeLabelsOpen}
            >
              <span>
                Node Labels
                <span className="ml-1.5 normal-case font-normal text-zinc-500">
                  ({metadata.node_labels.length})
                </span>
              </span>
              <span className="text-[10px]">{nodeLabelsOpen ? '▲' : '▼'}</span>
            </button>
            {nodeLabelsOpen && (
              <div className="mb-1">
                {metadata.node_labels.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-zinc-500 italic">No node labels</p>
                ) : (
                  metadata.node_labels.map((label) => (
                    <NodeLabelRow
                      key={label.label}
                      label={label}
                      onQueryTemplate={onQueryTemplate}
                    />
                  ))
                )}
              </div>
            )}

            {/* Edge Labels section */}
            <button
              type="button"
              onClick={() => setEdgeLabelsOpen(!edgeLabelsOpen)}
              className="w-full flex items-center justify-between px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wide hover:bg-zinc-700/50 transition-colors border-t border-zinc-700/60"
              aria-expanded={edgeLabelsOpen}
            >
              <span>
                Edge Labels
                <span className="ml-1.5 normal-case font-normal text-zinc-500">
                  ({metadata.edge_labels.length})
                </span>
              </span>
              <span className="text-[10px]">{edgeLabelsOpen ? '▲' : '▼'}</span>
            </button>
            {edgeLabelsOpen && (
              <div className="mb-1">
                {metadata.edge_labels.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-zinc-500 italic">No edge labels</p>
                ) : (
                  metadata.edge_labels.map((label) => (
                    <EdgeLabelRow
                      key={label.label}
                      label={label}
                      onQueryTemplate={onQueryTemplate}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        )}

        <LibraryPanel onQueryTemplate={onQueryTemplate} />
      </div>
    </div>
  )
}
