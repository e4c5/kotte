import { useMemo } from 'react'

export interface InspectorNode {
  id: string
  label: string
  properties: Record<string, unknown>
}

export interface InspectorEdge {
  id: string
  label: string
  source: string | { id: string }
  target: string | { id: string }
  properties: Record<string, unknown>
}

interface InspectorPanelProps {
  isOpen: boolean
  onClose: () => void
  nodes: InspectorNode[]
  edges: InspectorEdge[]
  selectedNodeId: string | null
  selectedEdgeId: string | null
  nodeLabelColor?: (label: string) => string
}

function formatValue(value: unknown): string {
  if (value === null) return 'null'
  if (value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function InspectorPanel({
  isOpen,
  onClose,
  nodes,
  edges,
  selectedNodeId,
  selectedEdgeId,
  nodeLabelColor,
}: InspectorPanelProps) {
  const entity = useMemo(() => {
    if (selectedNodeId) {
      const node = nodes.find((n) => n.id === selectedNodeId)
      if (!node) return null
      return {
        type: 'node' as const,
        title: 'Node Details',
        label: node.label,
        data: {
          Id: node.id,
          label: node.label,
          ...node.properties,
        },
      }
    }
    if (selectedEdgeId) {
      const edge = edges.find((e) => e.id === selectedEdgeId)
      if (!edge) return null
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source?.id
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target?.id
      return {
        type: 'edge' as const,
        title: 'Edge Details',
        label: edge.label,
        data: {
          Id: edge.id,
          type: edge.label,
          source: sourceId,
          target: targetId,
          ...edge.properties,
        },
      }
    }
    return null
  }, [nodes, edges, selectedNodeId, selectedEdgeId])

  const labelColor = entity && entity.label && nodeLabelColor
    ? nodeLabelColor(entity.label)
    : undefined

  return (
    <div
      className={`fixed right-0 top-0 h-full w-80 bg-zinc-800 border-l border-zinc-700 shadow-xl flex flex-col transition-transform duration-300 ease-out z-40 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
      aria-hidden={!isOpen}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700">
        <h2 className="text-sm font-semibold text-zinc-100 uppercase tracking-wide">
          Inspector
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-700 transition-colors"
          aria-label="Close inspector"
        >
          <span className="text-lg leading-none">×</span>
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {!entity && (
          <p className="text-zinc-500 text-sm">Select a node or edge on the graph to view details.</p>
        )}
        {entity && (
          <div className="space-y-4">
            <div>
              <span
                className="inline-block rounded-full px-3 py-1 text-xs font-semibold text-white"
                style={labelColor ? { backgroundColor: labelColor } : undefined}
              >
                {entity.label}
              </span>
            </div>
            <div>
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">
                {entity.title}
              </h3>
              <table className="w-full text-sm">
                <tbody className="text-zinc-300">
                  {Object.entries(entity.data).map(([key, value]) => (
                    <tr key={key} className="border-b border-zinc-700/50">
                      <td className="py-2 pr-3 font-medium text-zinc-400 align-top w-1/3">
                        {key}:
                      </td>
                      <td className="py-2 break-all">
                        {formatValue(value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
