import { useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'
import { useGraphStore, type LayoutType, type LabelStyle } from '../stores/graphStore'

export interface GraphNode {
  id: string
  label: string
  properties: Record<string, unknown>
  x?: number
  y?: number
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

interface GraphViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  width?: number
  height?: number
  onNodeClick?: (node: GraphNode) => void
  onNodeRightClick?: (node: GraphNode, event: MouseEvent) => void
  onExportReady?: (exportFn: () => Promise<void>) => void
}

export default function GraphView({
  nodes,
  edges,
  width = 800,
  height = 600,
  onNodeClick,
  onNodeRightClick,
  onExportReady,
}: GraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null)
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
    if (field === 'label') return node.label
    return String(node.properties[field] || node.id)
  }

  useEffect(() => {
    if (!svgRef.current || filteredNodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Set up zoom
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Create container for zoomable content
    const container = svg.append('g')

    // Initialize positions based on layout
    const nodesWithPositions = initializeLayout(filteredNodes, layout, width, height)

    // Create force simulation
    let simulation: d3.Simulation<GraphNode, GraphEdge>

    if (layout === 'force') {
      simulation = d3
        .forceSimulation<GraphNode>(nodesWithPositions)
        .force(
          'link',
          d3
            .forceLink<GraphNode, GraphEdge>(filteredEdges)
            .id((d) => d.id)
            .distance(100)
        )
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30))
    } else {
      // For non-force layouts, create a minimal simulation just for updates
      simulation = d3
        .forceSimulation<GraphNode>(nodesWithPositions)
        .force('center', d3.forceCenter(width / 2, height / 2))
        .alpha(0)
        .stop()
    }

    // Pin nodes that should be pinned
    nodesWithPositions.forEach((node) => {
      if (pinnedNodes.has(node.id)) {
        node.fx = node.x || width / 2
        node.fy = node.y || height / 2
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
      .attr('stroke', (d) => getEdgeStyle(d).color)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => getEdgeStyle(d).size)

    // Draw nodes
    const node = container
      .append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(filteredNodes)
      .enter()
      .append('circle')
      .attr('r', (d) => getNodeStyle(d).size)
      .attr('fill', (d) => getNodeStyle(d).color)
      .attr('stroke', (d) => (selectedNode === d.id ? '#ff0000' : '#fff'))
      .attr('stroke-width', (d) => (selectedNode === d.id ? 3 : 2))
      .style('cursor', 'pointer')
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
      .style('fill', '#333')

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => {
          const source = d.source as GraphNode
          return source.x || 0
        })
        .attr('y1', (d) => {
          const source = d.source as GraphNode
          return source.y || 0
        })
        .attr('x2', (d) => {
          const target = d.target as GraphNode
          return target.x || 0
        })
        .attr('y2', (d) => {
          const target = d.target as GraphNode
          return target.y || 0
        })

      node.attr('cx', (d) => d.x || 0).attr('cy', (d) => d.y || 0)

      labels.attr('x', (d) => d.x || 0).attr('y', (d) => d.y || 0)
    })

    // Cleanup
    return () => {
      simulation.stop()
    }
  }, [
    filteredNodes,
    filteredEdges,
    width,
    height,
    layout,
    nodeStyles,
    edgeStyles,
    selectedNode,
    pinnedNodes,
    onNodeClick,
    onNodeRightClick,
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
          canvas.width = width
          canvas.height = height
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
  }, [onExportReady, filteredNodes, filteredEdges, width, height])

  return (
    <div style={{ width: '100%', height: '100%', border: '1px solid #ccc' }}>
      <svg ref={svgRef} width={width} height={height} style={{ display: 'block' }} />
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
      // Force layout will be handled by simulation
      nodes.forEach((node) => {
        if (!node.x) node.x = centerX + (Math.random() - 0.5) * 100
        if (!node.y) node.y = centerY + (Math.random() - 0.5) * 100
      })
      break
    }
  }

  return nodes
}

