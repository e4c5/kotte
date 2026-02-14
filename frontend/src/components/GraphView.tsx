import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

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
}

export default function GraphView({
  nodes,
  edges,
  width = 800,
  height = 600,
  onNodeClick,
  onNodeRightClick,
}: GraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null)

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return

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

    // Create force simulation
    const simulation = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(edges)
          .id((d) => d.id)
          .distance(100)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30))

    simulationRef.current = simulation

    // Draw edges
    const link = container
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edges)
      .enter()
      .append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2)

    // Draw nodes
    const node = container
      .append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('r', 10)
      .attr('fill', (d) => getNodeColor(d.label))
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(
        d3
          .drag<SVGCircleElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x
            d.fy = d.y
          })
          .on('drag', (event, d) => {
            d.fx = event.x
            d.fy = event.y
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            d.fx = null
            d.fy = null
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
      .data(nodes)
      .enter()
      .append('text')
      .text((d) => d.label || d.id)
      .attr('font-size', '12px')
      .attr('dx', 15)
      .attr('dy', 4)
      .style('pointer-events', 'none')

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as GraphNode).x || 0)
        .attr('y1', (d) => (d.source as GraphNode).y || 0)
        .attr('x2', (d) => (d.target as GraphNode).x || 0)
        .attr('y2', (d) => (d.target as GraphNode).y || 0)

      node.attr('cx', (d) => d.x || 0).attr('cy', (d) => d.y || 0)

      labels.attr('x', (d) => d.x || 0).attr('y', (d) => d.y || 0)
    })

    // Cleanup
    return () => {
      simulation.stop()
    }
  }, [nodes, edges, width, height, onNodeClick, onNodeRightClick])

  return (
    <div style={{ width: '100%', height: '100%', border: '1px solid #ccc' }}>
      <svg ref={svgRef} width={width} height={height} style={{ display: 'block' }} />
    </div>
  )
}

// Color mapping for node labels
const colorScale = d3.scaleOrdinal(d3.schemeCategory10)

function getNodeColor(label: string): string {
  return colorScale(label) || '#999'
}

