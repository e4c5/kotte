import { useGraphStore } from '../stores/graphStore'
import type { GraphNode } from './GraphView'

interface LassoActionBarProps {
  filteredNodes: GraphNode[]
  onNodeDoubleClick?: (node: GraphNode) => void
}

export default function LassoActionBar({ filteredNodes, onNodeDoubleClick }: LassoActionBarProps) {
  const { lassoNodes, togglePinNode, toggleHideNode, clearLassoNodes } = useGraphStore()

  if (lassoNodes.size === 0) return null

  const nodeById = new Map(filteredNodes.map((n) => [n.id, n]))

  function pinAll() {
    lassoNodes.forEach((id) => togglePinNode(id))
  }

  function hideAll() {
    lassoNodes.forEach((id) => toggleHideNode(id))
    clearLassoNodes()
  }

  function expandAll() {
    if (!onNodeDoubleClick) return
    lassoNodes.forEach((id) => {
      const n = nodeById.get(id)
      if (n) onNodeDoubleClick(n)
    })
  }

  const btnCls =
    'h-7 rounded px-2 text-xs font-medium text-zinc-200 bg-zinc-800 hover:bg-zinc-700 border border-zinc-600/60'

  return (
    <div className="absolute left-1/2 -translate-x-1/2 top-3 z-30 flex items-center gap-1.5 rounded border border-blue-500/40 bg-zinc-900/95 px-3 py-1.5 shadow-lg">
      <span className="text-xs text-blue-300 font-medium mr-1">{lassoNodes.size} selected</span>
      <button type="button" onClick={pinAll} className={btnCls} title="Pin all selected nodes">
        Pin all
      </button>
      <button type="button" onClick={hideAll} className={btnCls} title="Hide all selected nodes">
        Hide all
      </button>
      {onNodeDoubleClick && (
        <button type="button" onClick={expandAll} className={btnCls} title="Expand all selected nodes">
          Expand all
        </button>
      )}
      <button
        type="button"
        onClick={clearLassoNodes}
        className="h-7 w-7 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-600/60 text-zinc-400 hover:text-zinc-200 text-sm leading-none"
        title="Clear selection"
        aria-label="Clear selection"
      >
        ✕
      </button>
    </div>
  )
}
