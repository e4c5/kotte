import { useEffect, useRef, useMemo, useState } from 'react'
import * as d3 from 'd3'
import { useGraphStore, type LayoutType, type LabelStyle } from '../stores/graphStore'

export interface GraphNode {
  id: string
  label: string
  properties: Record<string, unknown>
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

export interface GraphEdge {
  id: string
  label: string
  source: string | GraphNode
  target: string | GraphNode
  properties: Record<string, unknown>
}

export interface PathHighlights {
  nodeIds: string[]
  edgeIds: string[]
}

interface GraphViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  width?: number
  height?: number
  pathHighlights?: PathHighlights
  onNodeClick?: (node: GraphNode) => void
  onNodeRightClick?: (node: GraphNode, event: MouseEvent) => void
  onEdgeClick?: (edge: GraphEdge) => void
  onExportReady?: (exportFn: () => Promise<void>) => void
}

export default function GraphView({
  nodes,
  edges,
  width = 800,
  height = 600,
  pathHighlights,
  onNodeClick,
  onNodeRightClick,
  onEdgeClick,
  onExportReady,
}: GraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null)
  const [debugFitScale, setDebugFitScale] = useState<number | null>(null)
  const [resolvedSize, setResolvedSize] = useState({ width, height })
  const {
    layout,
    nodeStyles,
    edgeStyles,
    edgeWidthMapping,
    filters,
    selectedNode,
    pinnedNodes,
    hiddenNodes,
  } = useGraphStore()

  // Apply filters
  const filteredNodes = useMemo(() => {
    let filtered = nodes.filter((node) => !hiddenNodes.has(node.id))

    // Filter by label
    if (filters.nodeLabels.size > 0) {
      filtered = filtered.filter((node) => filters.nodeLabels.has(node.label))
    }

    // Filter by properties
    if (filters.propertyFilters.length > 0) {
      filtered = filtered.filter((node) => {
        return filters.propertyFilters.every((filter) => {
          if (filter.label && filter.label !== node.label) return true
          const propValue = String(node.properties[filter.property] || '')
          const filterValue = filter.value.toLowerCase()

          switch (filter.operator) {
            case 'equals':
              return propValue.toLowerCase() === filterValue
            case 'contains':
              return propValue.toLowerCase().includes(filterValue)
            case 'startsWith':
              return propValue.toLowerCase().startsWith(filterValue)
            case 'endsWith':
              return propValue.toLowerCase().endsWith(filterValue)
            default:
              return true
          }
        })
      })
    }

    return filtered
  }, [nodes, filters, hiddenNodes])

  const pathNodeIds = useMemo(
    () => new Set(pathHighlights?.nodeIds?.map(String) ?? []),
    [pathHighlights?.nodeIds]
  )
  const pathEdgeIds = useMemo(
    () => new Set(pathHighlights?.edgeIds?.map(String) ?? []),
    [pathHighlights?.edgeIds]
  )

  const filteredEdges = useMemo(() => {
    let filtered = edges.filter((edge) => {
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id
      return !hiddenNodes.has(sourceId) && !hiddenNodes.has(targetId)
    })

    // Filter by label
    if (filters.edgeLabels.size > 0) {
      filtered = filtered.filter((edge) => filters.edgeLabels.has(edge.label))
    }

    // Only include edges between visible nodes
    const visibleNodeIds = new Set(filteredNodes.map((n) => n.id))
    filtered = filtered.filter((edge) => {
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id
      return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId)
    })

    return filtered
  }, [edges, filters, hiddenNodes, filteredNodes])

  // Get style for node/edge
  const getNodeStyle = (node: GraphNode): LabelStyle => {
    return nodeStyles[node.label] || {
      color: getDefaultNodeColor(node.label),
      size: 10,
      captionField: 'label',
    }
  }

  // Compute edge width mapping scale if enabled
  const edgeWidthScale = useMemo(() => {
    if (!edgeWidthMapping.enabled || !edgeWidthMapping.property) {
      return null
    }
    
    const allValues = filteredEdges
      .map((e) => {
        const val = e.properties[edgeWidthMapping.property!]
        if (val === undefined || val === null) return null
        const num = typeof val === 'number' ? val : parseFloat(String(val))
        return isNaN(num) ? null : num
      })
      .filter((v): v is number => v !== null)
    
    if (allValues.length === 0) {
      return null
    }
    
    const minVal = Math.min(...allValues)
    const maxVal = Math.max(...allValues)
    
    if (edgeWidthMapping.scaleType === 'log' && minVal > 0) {
      return d3.scaleLog().domain([minVal, maxVal]).range([edgeWidthMapping.minWidth, edgeWidthMapping.maxWidth])
    } else {
      return d3.scaleLinear().domain([minVal, maxVal]).range([edgeWidthMapping.minWidth, edgeWidthMapping.maxWidth])
    }
  }, [filteredEdges, edgeWidthMapping])

  const getEdgeStyle = (edge: GraphEdge): LabelStyle => {
    const baseStyle = edgeStyles[edge.label] || {
      color: '#999',
      size: 2,
    }
    
    // Apply width mapping if enabled
    if (edgeWidthScale && edgeWidthMapping.property) {
      const propValue = edge.properties[edgeWidthMapping.property]
      if (propValue !== undefined && propValue !== null) {
        try {
          const numValue = typeof propValue === 'number' ? propValue : parseFloat(String(propValue))
          if (!isNaN(numValue)) {
            const mappedWidth = edgeWidthScale(numValue)
            return {
              ...baseStyle,
              size: mappedWidth,
            }
          }
        } catch (e) {
          // If mapping fails, use base style
        }
      }
    }
    
    return baseStyle
  }

  const getNodeCaption = (node: GraphNode): string => {
    const style = getNodeStyle(node)
    const field = style.captionField || 'label'
    let caption: string
    if (field === 'label') {
      caption = node.label
    } else {
      caption = String(node.properties[field] ?? node.id)
    }
    // If caption is the graph label (e.g. "CodeElement") and we have properties, use a descriptive property
    if (caption === node.label && node.properties && typeof node.properties === 'object') {
      const p = node.properties as Record<string, unknown>
      const name = p.name ?? p.title ?? p.fqn ?? p.signature
      if (name != null && String(name).trim() !== '') {
        const s = String(name)
        // Shorten long FQN/signature: show last segment if longer than 40 chars
        if (s.length > 40 && (s.includes('.') || s.includes('#'))) {
          const last = s.includes('#') ? s.split('#').pop()! : s.split('.').pop()!
          return last
        }
        return s
      }
    }
    return caption
  }

  useEffect(() => {
    if (!svgRef.current || filteredNodes.length === 0) return

    const svgEl = svgRef.current
    const containerRect = svgEl.parentElement?.getBoundingClientRect()
    const measuredWidth = Math.floor(containerRect?.width ?? 0)
    const measuredHeight = Math.floor(containerRect?.height ?? 0)
    // Prefer measured container size to avoid oversized SVG causing page scrollbars.
    const viewportWidth = Math.max(measuredWidth > 0 ? measuredWidth : width, 1)
    const viewportHeight = Math.max(measuredHeight > 0 ? measuredHeight : height, 1)
    setResolvedSize((prev) =>
      prev.width === viewportWidth && prev.height === viewportHeight
        ? prev
        : { width: viewportWidth, height: viewportHeight }
    )

    const svg = d3.select(svgEl)
    svg.selectAll('*').remove()

    // Create container for zoomable content (must be defined before zoom handler)
    const container = svg.append('g')

    // Set up zoom
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 20])
      .on('zoom', (event) => {
        container.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Initialize positions based on layout
    const nodesWithPositions = initializeLayout(filteredNodes, layout, viewportWidth, viewportHeight)

    // When there are no edges, force-directed layout has nothing to optimize (no links);
    // repulsion alone pushes nodes to the boundaries. Use static layout only (no simulation).
    const hasEdges = filteredEdges.length > 0

    // Create force simulation (or static "simulation" for rendering only)
    let simulation: d3.Simulation<GraphNode, GraphEdge>

    if (layout === 'force' && hasEdges) {
      // Run real force simulation: default alpha (1) and alphaDecay (~0.028) so it runs
      // enough ticks to reach equilibrium (D3 default ~300 iterations).
      simulation = d3
        .forceSimulation<GraphNode>(nodesWithPositions)
        .alpha(1)
        .alphaDecay(0.05)
        .velocityDecay(0.45)
        .force(
          'link',
          d3
            .forceLink<GraphNode, GraphEdge>(filteredEdges)
            .id((d) => d.id)
            .distance(90)
        )
        .force('charge', d3.forceManyBody().strength(-110))
        .force('center', d3.forceCenter(viewportWidth / 2, viewportHeight / 2))
        .force('x', d3.forceX(viewportWidth / 2).strength(0.04))
        .force('y', d3.forceY(viewportHeight / 2).strength(0.04))
        .force('collision', d3.forceCollide().radius(28))
    } else {
      // Static layout: grid/circle/radial already set in initializeLayout; no forces, no run.
      simulation = d3
        .forceSimulation<GraphNode>(nodesWithPositions)
        .alpha(0)
        .stop()
    }

    // Pin nodes that should be pinned
    nodesWithPositions.forEach((node) => {
      if (pinnedNodes.has(node.id)) {
        node.fx = node.x || viewportWidth / 2
        node.fy = node.y || viewportHeight / 2
      }
    })

    simulationRef.current = simulation

    // Draw edges
    const link = container
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(filteredEdges)
      .enter()
      .append('line')
      .attr('stroke', (d) =>
        pathEdgeIds.has(String(d.id)) ? '#0066cc' : getEdgeStyle(d).color
      )
      .attr('stroke-opacity', (d) => (pathEdgeIds.has(String(d.id)) ? 1 : 0.6))
      .attr('stroke-width', (d) =>
        pathEdgeIds.has(String(d.id)) ? Math.max(3, getEdgeStyle(d).size) : getEdgeStyle(d).size
      )

    if (onEdgeClick) {
      link
        .style('cursor', 'pointer')
        .on('click', (event: MouseEvent, d: GraphEdge) => {
          event.stopPropagation()
          onEdgeClick(d)
        })
    }

    // Draw nodes
    const node = container
      .append('g')
      .attr('class', 'nodes')
      .attr('role', 'group')
      .attr('aria-label', 'Graph nodes')
      .selectAll('circle')
      .data(filteredNodes)
      .enter()
      .append('circle')
      .attr('r', (d) => getNodeStyle(d).size)
      .attr('fill', (d) =>
        pathNodeIds.has(d.id) ? '#0066cc' : getNodeStyle(d).color
      )
      .attr('stroke', (d) => {
        if (selectedNode === d.id) return '#ff0000'
        if (pathNodeIds.has(d.id)) return '#004499'
        return '#fff'
      })
      .attr('stroke-width', (d) => {
        if (selectedNode === d.id) return 3
        if (pathNodeIds.has(d.id)) return 3
        return 2
      })
      .style('cursor', 'pointer')
      .attr('role', 'button')
      .attr('tabindex', 0)
      .attr('aria-label', (d) => `Node: ${d.label}, ID: ${d.id}`)
      .attr('aria-pressed', (d) => selectedNode === d.id)
      .call(
        d3
          .drag<SVGCircleElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active && layout === 'force') {
              simulation.alphaTarget(0.3).restart()
            }
            if (!pinnedNodes.has(d.id)) {
              d.fx = d.x
              d.fy = d.y
            }
          })
          .on('drag', (event, d) => {
            if (!pinnedNodes.has(d.id)) {
              d.fx = event.x
              d.fy = event.y
            }
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            if (!pinnedNodes.has(d.id)) {
              d.fx = null
              d.fy = null
            }
          })
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        onNodeClick?.(d)
      })
      .on('contextmenu', (event, d) => {
        event.preventDefault()
        onNodeRightClick?.(d, event)
      })

    // Add labels
    const labels = container
      .append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(filteredNodes)
      .enter()
      .append('text')
      .text((d) => getNodeCaption(d))
      .attr('font-size', '12px')
      .attr('dx', (d) => getNodeStyle(d).size + 5)
      .attr('dy', 4)
      .style('pointer-events', 'none')
      .style('fill', '#e4e4e7')

    // Bounds for force-directed layout (only applied when simulation is running)
    const padding = 60
    const xMin = padding
    const xMax = viewportWidth - padding
    const yMin = padding
    const yMax = viewportHeight - padding

    const centerX = viewportWidth / 2
    const centerY = viewportHeight / 2

    // Helper: zoom/pan so that all nodes fit nicely in view
    const fitToView = (animate = true) => {
      if (!nodesWithPositions.length) return
      const xs = nodesWithPositions.map((n) => n.x ?? centerX)
      const ys = nodesWithPositions.map((n) => n.y ?? centerY)
      const minX = Math.min(...xs)
      const maxX = Math.max(...xs)
      const minY = Math.min(...ys)
      const maxY = Math.max(...ys)
      const contentWidth = maxX - minX || 1
      const contentHeight = maxY - minY || 1

      // Leave some margin around the graph
      const margin = 40
      const scaleX = (viewportWidth - 2 * margin) / contentWidth
      const scaleY = (viewportHeight - 2 * margin) / contentHeight
      const rawScale = 0.92 * Math.min(scaleX, scaleY)
      const scale = Math.max(0.1, rawScale)
      setDebugFitScale(scale)

      const tx = centerX - scale * (minX + contentWidth / 2)
      const ty = centerY - scale * (minY + contentHeight / 2)

      const transform = d3.zoomIdentity.translate(tx, ty).scale(scale)
      if (animate) {
        svg.transition().duration(400).call(zoom.transform, transform)
      } else {
        svg.call(zoom.transform, transform)
      }
    }

    // Resolve link endpoint to node (source/target may be string ID when no link force is used)
    const nodeById = new Map(nodesWithPositions.map((n) => [n.id, n]))
    const getNode = (endpoint: string | GraphNode): GraphNode | undefined =>
      typeof endpoint === 'string' ? nodeById.get(endpoint) : endpoint

    // Update positions on simulation tick (and initial render for static layout)
    let didAutoStop = false
    function applyPositions() {
      if (layout === 'force' && hasEdges) {
        nodesWithPositions.forEach((n) => {
          if (n.fx != null && n.fy != null) return // pinned
          if ((n.x ?? centerX) < xMin) {
            n.x = xMin
            n.vx = (n.vx ?? 0) * -0.25
          } else if ((n.x ?? centerX) > xMax) {
            n.x = xMax
            n.vx = (n.vx ?? 0) * -0.25
          }

          if ((n.y ?? centerY) < yMin) {
            n.y = yMin
            n.vy = (n.vy ?? 0) * -0.25
          } else if ((n.y ?? centerY) > yMax) {
            n.y = yMax
            n.vy = (n.vy ?? 0) * -0.25
          }
        })

        if (!didAutoStop && simulation.alpha() < 0.035) {
          didAutoStop = true
          simulation.stop()
          fitToView()
        }
      }

      link
        .attr('x1', (d) => getNode(d.source)?.x ?? centerX)
        .attr('y1', (d) => getNode(d.source)?.y ?? centerY)
        .attr('x2', (d) => getNode(d.target)?.x ?? centerX)
        .attr('y2', (d) => getNode(d.target)?.y ?? centerY)

      node.attr('cx', (d) => d.x ?? centerX).attr('cy', (d) => d.y ?? centerY)
      labels.attr('x', (d) => d.x ?? centerX).attr('y', (d) => d.y ?? centerY)
    }

    simulation.on('tick', applyPositions)

    // Static layout: apply initial positions immediately so graph is visible without waiting for tick
    if (layout !== 'force' || !hasEdges) {
      applyPositions()
      simulation.tick()
      // For static layouts, immediately fit to view
      fitToView(false)
    }

    // After a force simulation, fit once it settles
    let forceFitTimer: number | null = null
    let forceStopTimer: number | null = null
    if (layout === 'force' && hasEdges) {
      // Ensure graph fills the viewport even if simulation is interrupted/restarted.
      forceFitTimer = window.setTimeout(() => {
        applyPositions()
        fitToView(false)
      }, 800)

      // Hard cap to prevent endless animation in high-energy/degenerate graphs.
      forceStopTimer = window.setTimeout(() => {
        simulation.stop()
        applyPositions()
        fitToView()
      }, 3500)

      simulation.on('end', () => {
        if (forceStopTimer !== null) {
          window.clearTimeout(forceStopTimer)
          forceStopTimer = null
        }
        applyPositions()
        fitToView()
      })
    }

    // Cleanup
    return () => {
      if (forceFitTimer !== null) {
        window.clearTimeout(forceFitTimer)
      }
      if (forceStopTimer !== null) {
        window.clearTimeout(forceStopTimer)
      }
      simulation.stop()
    }
  }, [
    filteredNodes,
    filteredEdges,
    pathNodeIds,
    pathEdgeIds,
    width,
    height,
    layout,
    nodeStyles,
    edgeStyles,
    selectedNode,
    pinnedNodes,
    onNodeClick,
    onNodeRightClick,
    onEdgeClick,
  ])

  // Export to PNG function
  const exportToPNG = async (): Promise<void> => {
    if (!svgRef.current) {
      throw new Error('SVG element not found')
    }

    const svg = svgRef.current
    
    // Clone the SVG to avoid modifying the original
    const clonedSvg = svg.cloneNode(true) as SVGSVGElement
    
    // Get the transform from the zoom container
    const container = svg.querySelector('g')
    if (container) {
      const transform = container.getAttribute('transform')
      if (transform) {
        // Apply transform to all children
        const children = clonedSvg.querySelector('g')
        if (children) {
          children.setAttribute('transform', transform)
        }
      }
    }
    
    // Serialize SVG to string
    const serializer = new XMLSerializer()
    const svgString = serializer.serializeToString(clonedSvg)
    
    // Create a data URL
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)
    
    // Create an image element
    const img = new Image()
    
    return new Promise((resolve, reject) => {
      img.onload = () => {
        try {
          // Create a canvas
        const canvas = document.createElement('canvas')
          canvas.width = resolvedSize.width
          canvas.height = resolvedSize.height
          const ctx = canvas.getContext('2d')
          
          if (!ctx) {
            reject(new Error('Could not get canvas context'))
            return
          }
          
          // Fill white background
          ctx.fillStyle = 'white'
          ctx.fillRect(0, 0, canvas.width, canvas.height)
          
          // Draw the image onto the canvas
          ctx.drawImage(img, 0, 0)
          
          // Convert canvas to PNG blob
          canvas.toBlob((blob) => {
            if (!blob) {
              reject(new Error('Failed to create PNG blob'))
              return
            }
            
            // Create download link
            const downloadUrl = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = downloadUrl
            link.download = `graph-export-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            
            // Cleanup
            URL.revokeObjectURL(url)
            URL.revokeObjectURL(downloadUrl)
            
            resolve()
          }, 'image/png')
        } catch (error) {
          URL.revokeObjectURL(url)
          reject(error)
        }
      }
      
      img.onerror = () => {
        URL.revokeObjectURL(url)
        reject(new Error('Failed to load SVG image'))
      }
      
      img.src = url
    })
  }

  // Expose export function to parent
  useEffect(() => {
    if (onExportReady) {
      onExportReady(exportToPNG)
    }
  }, [onExportReady, filteredNodes, filteredEdges, width, height, resolvedSize.width, resolvedSize.height])

  return (
    <div className="w-full h-full bg-zinc-950 relative">
      <div className="absolute left-2 top-2 z-10 pointer-events-none rounded bg-emerald-500/20 border border-emerald-400/40 px-2 py-1 text-[10px] text-emerald-300 font-mono">
        GraphView marker: 2026-02-23-v3 | prop:{width}x{height} | view:{resolvedSize.width}x{resolvedSize.height} | fit:{debugFitScale?.toFixed(2) ?? 'n/a'}
      </div>
      <svg ref={svgRef} width={resolvedSize.width} height={resolvedSize.height} className="block" />
    </div>
  )
}

// Color mapping for node labels
const colorScale = d3.scaleOrdinal(d3.schemeCategory10)

function getDefaultNodeColor(label: string): string {
  return colorScale(label) || '#999'
}

// Initialize node positions based on layout type
function initializeLayout(
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
