import * as d3 from 'd3'
import type { GraphNode } from '../components/GraphView'
import type { LayoutType } from '../stores/graphStore'

type HierarchyNodeData = {
  name: string
  node?: GraphNode
  children?: HierarchyNodeData[]
}

// Initialize node positions based on layout type
export function initializeLayout(
  nodes: GraphNode[],
  layout: LayoutType,
  width: number,
  height: number
): GraphNode[] {
  const centerX = width / 2
  const centerY = height / 2

  switch (layout) {
    case 'hierarchical': {
      // Simple hierarchical: arrange by label, then by id
      const labels = Array.from(new Set(nodes.map((n) => n.label)))
      const nodesByLabel = labels.map((label) =>
        nodes.filter((n) => n.label === label)
      )

      nodesByLabel.forEach((labelNodes, labelIdx) => {
        const rows = Math.ceil(Math.sqrt(labelNodes.length))
        const cols = Math.ceil(labelNodes.length / rows)
        const cellWidth = width / (cols + 1)
        const cellHeight = height / (rows + 1)

        labelNodes.forEach((node, idx) => {
          const row = Math.floor(idx / cols)
          const col = idx % cols
          node.x = (col + 1) * cellWidth
          node.y = (row + 1) * cellHeight + labelIdx * 50
        })
      })
      break
    }

    case 'radial': {
      const angleStep = (2 * Math.PI) / nodes.length
      const radius = Math.min(width, height) * 0.3

      nodes.forEach((node, idx) => {
        const angle = idx * angleStep
        node.x = centerX + radius * Math.cos(angle)
        node.y = centerY + radius * Math.sin(angle)
      })
      break
    }

    case 'grid': {
      const cols = Math.ceil(Math.sqrt(nodes.length))
      const rows = Math.ceil(nodes.length / cols)
      const cellWidth = width / (cols + 1)
      const cellHeight = height / (rows + 1)

      nodes.forEach((node, idx) => {
        const row = Math.floor(idx / cols)
        const col = idx % cols
        node.x = (col + 1) * cellWidth
        node.y = (row + 1) * cellHeight
      })
      break
    }

    case 'random': {
      nodes.forEach((node) => {
        node.x = Math.random() * width
        node.y = Math.random() * height
      })
      break
    }

    case 'cluster': {
      if (!nodes.length) break

      const groups = new Map<string, GraphNode[]>()
      nodes.forEach((node) => {
        const key = node.label || 'Other'
        const group = groups.get(key)
        if (group) {
          group.push(node)
        } else {
          groups.set(key, [node])
        }
      })

      const entries = Array.from(groups.entries())
      const numGroups = entries.length
      const padding = 48
      const usableWidth = width - 2 * padding
      const usableHeight = height - 2 * padding
      const colWidth = numGroups > 0 ? usableWidth / numGroups : usableWidth

      entries.forEach(([, groupNodes], groupIdx) => {
        const n = groupNodes.length
        const rows = Math.max(1, Math.ceil(Math.sqrt(n)))
        const cols = Math.max(1, Math.ceil(n / rows))
        const cellW = colWidth / (cols + 1)
        const cellH = usableHeight / (rows + 1)
        const baseX = padding + groupIdx * colWidth

        groupNodes.forEach((node, idx) => {
          const row = Math.floor(idx / cols)
          const col = idx % cols
          node.x = baseX + (col + 1) * cellW
          node.y = padding + (row + 1) * cellH
        })
      })

      break
    }

    case 'partition': {
      if (!nodes.length) break

      const groups = new Map<string, GraphNode[]>()
      nodes.forEach((node) => {
        const key = node.label || 'Other'
        const group = groups.get(key)
        if (group) {
          group.push(node)
        } else {
          groups.set(key, [node])
        }
      })

      const rootData: HierarchyNodeData = {
        name: 'root',
        children: Array.from(groups.entries()).map(([label, groupNodes]) => ({
          name: label,
          children: groupNodes.map((node) => ({
            name: String(node.id),
            node,
          })),
        })),
      }

      const root = d3
        .hierarchy<HierarchyNodeData>(rootData, (d) => d.children)
        .sum((d) => (d.node ? 1 : 0))

      // Sunburst: partition in polar space (angle, radius) then map to x,y
      const radius = Math.min(width, height) / 2 - 24
      const partitionLayout = d3
        .partition<HierarchyNodeData>()
        .size([2 * Math.PI, radius])
      partitionLayout(root)

      const byId = new Map(nodes.map((n) => [n.id, n]))
      root.leaves().forEach((leaf) => {
        const data = leaf.data.node
        if (!data) return
        const target = byId.get(data.id)
        if (!target) return
        const angle = (leaf.x0 + leaf.x1) / 2
        const r = (leaf.y0 + leaf.y1) / 2
        target.x = centerX + r * Math.cos(angle)
        target.y = centerY + r * Math.sin(angle)
      })

      break
    }

    case 'pack': {
      if (!nodes.length) break

      const groups = new Map<string, GraphNode[]>()
      nodes.forEach((node) => {
        const key = node.label || 'Other'
        const group = groups.get(key)
        if (group) {
          group.push(node)
        } else {
          groups.set(key, [node])
        }
      })

      const rootData: HierarchyNodeData = {
        name: 'root',
        children: Array.from(groups.entries()).map(([label, groupNodes]) => ({
          name: label,
          children: groupNodes.map((node) => ({
            name: String(node.id),
            node,
          })),
        })),
      }

      const root = d3
        .hierarchy<HierarchyNodeData>(rootData, (d) => d.children)
        .sum((d) => (d.node ? 1 : 0))

      const packLayout = d3
        .pack<HierarchyNodeData>()
        .size([width, height])
        .padding(8)
      packLayout(root)

      const byId = new Map(nodes.map((n) => [n.id, n]))
      root.leaves().forEach((leaf) => {
        const data = leaf.data.node
        if (!data) return
        const target = byId.get(data.id)
        if (!target) return
        target.x = leaf.x
        target.y = leaf.y
      })

      break
    }

    case 'force':
    default: {
      // Spread nodes in a grid over the full viewport so the graph uses available space from the start
      const padding = 60
      const xMin = padding
      const xMax = width - padding
      const yMin = padding
      const yMax = height - padding
      const usableWidth = Math.max(1, xMax - xMin)
      const usableHeight = Math.max(1, yMax - yMin)
      const n = nodes.length
      if (n > 0) {
        const cols = Math.ceil(Math.sqrt(n))
        const rows = Math.ceil(n / cols)
        const cellW = usableWidth / (cols + 1)
        const cellH = usableHeight / (rows + 1)
        nodes.forEach((node, idx) => {
          if (node.x == null && node.y == null) {
            const col = idx % cols
            const row = Math.floor(idx / cols)
            node.x = xMin + (col + 1) * cellW
            node.y = yMin + (row + 1) * cellH
          }
        })
      }
      break
    }
  }

  return nodes
}
