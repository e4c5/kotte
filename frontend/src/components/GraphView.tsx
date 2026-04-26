import { useEffect, useRef, useMemo, useState } from 'react'
import * as d3 from 'd3'
import { useGraphStore } from '../stores/graphStore'
import { initializeLayout } from '../utils/graphLayouts'
import { getNodeStyle, getEdgeStyle, getNodeCaption, getEdgeCaption } from '../utils/graphStyles'
import { linkPath, markerIdForColor, parallelEdgeMeta, type LinkPathResult } from '../utils/graphLinkPaths'
import { useGraphExport } from '../hooks/useGraphExport'
import GraphCanvas from './GraphCanvas'

// Switch to Canvas 2D renderer above this threshold (total nodes + edges).
// Lower than maxNodesForGraph so users with a raised cap still get a
// responsive canvas before the hard result limit kicks in.
const CANVAS_THRESHOLD_ENTER = 1500
const CANVAS_THRESHOLD_EXIT = 1350

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
  onNodeDoubleClick?: (node: GraphNode) => void
  onNodeRightClick?: (node: GraphNode, event: MouseEvent) => void
  onEdgeClick?: (edge: GraphEdge) => void
  onExportReady?: (exportFn: () => Promise<void>) => void
}

/** Applies precomputed path `d` from `pathByEdgeId` to a link or hit selection. */
function applyLinkPathD(
  sel: d3.Selection<SVGPathElement, GraphEdge, SVGGElement, unknown>,
  pathByEdgeId: Map<string, LinkPathResult>
) {
  sel.attr('d', (d) => pathByEdgeId.get(d.id)?.d ?? '')
}

export default function GraphView({
  nodes,
  edges,
  width = 800,
  height = 600,
  pathHighlights,
  onNodeClick,
  onNodeDoubleClick,
  onNodeRightClick,
  onEdgeClick,
  onExportReady,
}: GraphViewProps) {
  type SvgSelection = d3.Selection<SVGSVGElement, unknown, null, undefined>

  const svgRef = useRef<SVGSVGElement>(null)
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null)
  const svgSelectionRef = useRef<SvgSelection | null>(null)
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const fitToViewRef = useRef<(() => void) | null>(null)
  const zoomTransformRef = useRef(d3.zoomIdentity)
  const userZoomedRef = useRef(false)
  const applyingAutoTransformRef = useRef(false)
  // Camera-focus pin survives the store-triggered re-render. Holding the
  // timer + pinned-node-id at component scope (rather than as a local in
  // the camera-focus effect) means the effect cleanup that fires when
  // `clearCameraFocusAnchorIds()` flips the dep can't accidentally cancel
  // the still-pending 2 s release. Cleanup is centralised in
  // `releasePin` and the dedicated unmount effect below.
  const pinRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null
    id: string | null
  }>({ timer: null, id: null })
  const onNodeClickRef = useRef<typeof onNodeClick>(onNodeClick)
  const onNodeDoubleClickRef = useRef<typeof onNodeDoubleClick>(onNodeDoubleClick)
  const onNodeRightClickRef = useRef<typeof onNodeRightClick>(onNodeRightClick)
  const onEdgeClickRef = useRef<typeof onEdgeClick>(onEdgeClick)
  const [debugFitScale, setDebugFitScale] = useState<number | null>(null)
  const [resolvedSize, setResolvedSize] = useState({ width, height })
  const [canvasMode, setCanvasMode] = useState(false)
  const {
    layout,
    nodeStyles,
    edgeStyles,
    edgeWidthMapping,
    filters,
    selectedNode,
    pinnedNodes,
    hiddenNodes,
    cameraFocusAnchorIds,
    clearCameraFocusAnchorIds,
  } = useGraphStore()

  // Apply filters
  const filteredNodes = useMemo(() => {
    let filtered = nodes.filter((node) => !hiddenNodes.has(node.id))
    if (filters.nodeLabels.size > 0) {
      filtered = filtered.filter((node) => filters.nodeLabels.has(node.label))
    }
    if (filters.propertyFilters.length > 0) {
      filtered = filtered.filter((node) => {
        return filters.propertyFilters.every((filter) => {
          if (filter.label && filter.label !== node.label) return true
          const propValue = String(node.properties[filter.property] || '')
          const filterValue = filter.value.toLowerCase()
          switch (filter.operator) {
            case 'equals': return propValue.toLowerCase() === filterValue
            case 'contains': return propValue.toLowerCase().includes(filterValue)
            case 'startsWith': return propValue.toLowerCase().startsWith(filterValue)
            case 'endsWith': return propValue.toLowerCase().endsWith(filterValue)
            default: return true
          }
        })
      })
    }
    return filtered
  }, [nodes, filters, hiddenNodes])

  const pathNodeIds = useMemo(() => new Set(pathHighlights?.nodeIds?.map(String) ?? []), [pathHighlights?.nodeIds])
  const pathEdgeIds = useMemo(() => new Set(pathHighlights?.edgeIds?.map(String) ?? []), [pathHighlights?.edgeIds])

  useEffect(() => {
    onNodeClickRef.current = onNodeClick
    onNodeDoubleClickRef.current = onNodeDoubleClick
    onNodeRightClickRef.current = onNodeRightClick
    onEdgeClickRef.current = onEdgeClick
  }, [onNodeClick, onNodeDoubleClick, onNodeRightClick, onEdgeClick])

  const filteredEdges = useMemo(() => {
    let filtered = edges.filter((edge) => {
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id
      return !hiddenNodes.has(sourceId) && !hiddenNodes.has(targetId)
    })
    if (filters.edgeLabels.size > 0) {
      filtered = filtered.filter((edge) => filters.edgeLabels.has(edge.label))
    }
    const visibleNodeIds = new Set(filteredNodes.map((n) => n.id))
    return filtered.filter((edge) => {
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id
      return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId)
    })
  }, [edges, filters, hiddenNodes, filteredNodes])

  // Canvas-mode hysteresis: switch to canvas above ENTER threshold, back to SVG only when
  // count drops below EXIT threshold. Avoids oscillation when count hovers around the boundary.
  useEffect(() => {
    const total = filteredNodes.length + filteredEdges.length
    if (!canvasMode && total >= CANVAS_THRESHOLD_ENTER) setCanvasMode(true)
    if (canvasMode && total < CANVAS_THRESHOLD_EXIT) setCanvasMode(false)
  }, [filteredNodes.length, filteredEdges.length, canvasMode])

  useEffect(() => {
    userZoomedRef.current = false
    zoomTransformRef.current = d3.zoomIdentity
  }, [filteredNodes, filteredEdges, layout])

  const edgeWidthScale = useMemo(() => {
    if (!edgeWidthMapping.enabled || !edgeWidthMapping.property) return null
    const allValues = filteredEdges
      .map((e) => {
        const val = e.properties[edgeWidthMapping.property!]
        if (val === undefined || val === null) return null
        const num = typeof val === 'number' ? val : parseFloat(String(val))
        return isNaN(num) ? null : num
      })
      .filter((v): v is number => v !== null)
    if (allValues.length === 0) return null
    const minVal = Math.min(...allValues)
    const maxVal = Math.max(...allValues)
    return edgeWidthMapping.scaleType === 'log' && minVal > 0
      ? d3.scaleLog().domain([minVal, maxVal]).range([edgeWidthMapping.minWidth, edgeWidthMapping.maxWidth])
      : d3.scaleLinear().domain([minVal, maxVal]).range([edgeWidthMapping.minWidth, edgeWidthMapping.maxWidth])
  }, [filteredEdges, edgeWidthMapping])

  const { exportToPNG } = useGraphExport({
    svgRef,
    width: resolvedSize.width,
    height: resolvedSize.height,
  })

  useEffect(() => {
    if (onExportReady) onExportReady(exportToPNG)
  }, [onExportReady, exportToPNG])

  useEffect(() => {
    if (!svgRef.current) return
    const svgEl = svgRef.current
    const containerRect = svgEl.parentElement?.getBoundingClientRect()
    const viewportWidth = Math.max(Math.floor(containerRect?.width ?? width), 1)
    const viewportHeight = Math.max(Math.floor(containerRect?.height ?? height), 1)
    setResolvedSize((prev) => prev.width === viewportWidth && prev.height === viewportHeight ? prev : { width: viewportWidth, height: viewportHeight })

    const svg = d3.select(svgEl)
    svg.selectAll('*').remove()

    const edgeStrokeColor = (e: GraphEdge) =>
      pathEdgeIds.has(String(e.id))
        ? '#0066cc'
        : getEdgeStyle(e, edgeStyles, edgeWidthScale, edgeWidthMapping.property).color

    const edgeColors = new Set<string>()
    filteredEdges.forEach((e) => edgeColors.add(edgeStrokeColor(e)))
    const defs = svg.append('defs')
    edgeColors.forEach((color) => {
      const mid = markerIdForColor(color)
      defs
        .append('marker')
        .attr('id', mid)
        .attr('viewBox', '0 0 10 10')
        .attr('refX', 9)
        .attr('refY', 5)
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .attr('orient', 'auto')
        .attr('markerUnits', 'userSpaceOnUse')
        .append('path')
        .attr('d', 'M0,0 L10,5 L0,10 z')
        .attr('fill', color)
    })

    const container = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.05, 20]).on('zoom', (event) => {
      zoomTransformRef.current = event.transform
      if (!applyingAutoTransformRef.current) userZoomedRef.current = true
      container.attr('transform', event.transform)
    })
    svg.call(zoom)
    svgSelectionRef.current = svg
    zoomBehaviorRef.current = zoom

    const nodesWithPositions = initializeLayout(filteredNodes, layout, viewportWidth, viewportHeight)
    if (nodesWithPositions.length === 0) {
      fitToViewRef.current = null
      return
    }

    const hasEdges = filteredEdges.length > 0
    let simulation: d3.Simulation<GraphNode, GraphEdge>
    if (layout === 'force' && hasEdges) {
      simulation = d3.forceSimulation<GraphNode>(nodesWithPositions)
        .alpha(1).alphaDecay(0.05).velocityDecay(0.45)
        .force('link', d3.forceLink<GraphNode, GraphEdge>(filteredEdges).id((d) => d.id).distance(90))
        .force('charge', d3.forceManyBody().strength(-110))
        .force('center', d3.forceCenter(viewportWidth / 2, viewportHeight / 2))
        .force('x', d3.forceX(viewportWidth / 2).strength(0.04))
        .force('y', d3.forceY(viewportHeight / 2).strength(0.04))
        .force('collision', d3.forceCollide().radius(28))
    } else {
      simulation = d3.forceSimulation<GraphNode>(nodesWithPositions).alpha(0).stop()
    }

    nodesWithPositions.forEach((node) => {
      if (pinnedNodes.has(node.id)) {
        node.fx = node.x || viewportWidth / 2
        node.fy = node.y || viewportHeight / 2
      }
    })
    simulationRef.current = simulation

    const nodeStrokeColor = (d: GraphNode) => {
      if (selectedNode === d.id) return '#ff0000'
      if (pathNodeIds.has(d.id)) return '#004499'
      if (pinnedNodes.has(d.id)) return '#f59e0b'
      return '#fff'
    }

    const nodeStrokeWidth = (d: GraphNode) => {
      if (selectedNode === d.id || pathNodeIds.has(d.id)) return 3
      if (pinnedNodes.has(d.id)) return 3
      return 2
    }

    const parallelByEdgeId = parallelEdgeMeta(filteredEdges)
    const getNodeR = (n: GraphNode) => getNodeStyle(n, nodeStyles).size

    const linkGroup = container.append('g').attr('class', 'links')

    const linkHit = linkGroup
      .selectAll<SVGPathElement, GraphEdge>('path.link-hit')
      .data(filteredEdges)
      .enter()
      .append('path')
      .attr('class', 'link-hit')
      .attr('fill', 'none')
      .attr('stroke', 'transparent')
      .attr('stroke-width', 16)
      .attr('pointer-events', 'stroke')

    const link = linkGroup
      .selectAll<SVGPathElement, GraphEdge>('path.link-line')
      .data(filteredEdges)
      .enter()
      .append('path')
      .attr('class', 'link-line')
      .attr('fill', 'none')
      .attr('stroke', (d) => edgeStrokeColor(d))
      .attr('stroke-opacity', (d) => (pathEdgeIds.has(String(d.id)) ? 1 : 0.6))
      .attr('stroke-width', (d) =>
        pathEdgeIds.has(String(d.id))
          ? Math.max(3, getEdgeStyle(d, edgeStyles, edgeWidthScale, edgeWidthMapping.property).size)
          : getEdgeStyle(d, edgeStyles, edgeWidthScale, edgeWidthMapping.property).size
      )
      .attr('marker-end', (d) => `url(#${markerIdForColor(edgeStrokeColor(d))})`)
      .style('pointer-events', 'none')

    if (onEdgeClickRef.current) {
      linkHit
        .style('cursor', 'pointer')
        .attr('role', 'button')
        .attr('tabindex', 0)
        .attr('aria-label', (d) => `Edge: ${d.label}, ID: ${d.id}`)
        .on('click', (event: MouseEvent, d: GraphEdge) => {
          event.stopPropagation()
          onEdgeClickRef.current?.(d)
        })
        .on('keydown', (event: KeyboardEvent, d: GraphEdge) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            event.stopPropagation()
            onEdgeClickRef.current?.(d)
          }
        })
    }

    const node = container.append('g').attr('class', 'nodes').attr('role', 'group').attr('aria-label', 'Graph nodes').selectAll('circle').data(filteredNodes).enter().append('circle')
      .attr('r', (d) => getNodeStyle(d, nodeStyles).size)
      .attr('fill', (d) => pathNodeIds.has(d.id) ? '#0066cc' : getNodeStyle(d, nodeStyles).color)
      .attr('stroke', (d) => nodeStrokeColor(d))
      .attr('stroke-width', (d) => nodeStrokeWidth(d))
      .style('cursor', 'pointer').attr('role', 'button').attr('tabindex', 0).attr('aria-label', (d) => `Node: ${d.label}, ID: ${d.id}`).attr('aria-pressed', (d) => selectedNode === d.id)
      .call(d3.drag<SVGCircleElement, GraphNode>().on('start', (event, d) => {
        if (!event.active && layout === 'force') simulation.alphaTarget(0.3).restart()
        if (!pinnedNodes.has(d.id) && layout === 'force') { d.fx = d.x; d.fy = d.y }
      }).on('drag', (event, d) => {
        if (pinnedNodes.has(d.id)) return
        if (layout === 'force') { d.fx = event.x; d.fy = event.y } else { d.x = event.x; d.y = event.y }
        applyPositions()
      }).on('end', (event, d) => {
        if (layout !== 'force') {
          return
        }
        if (!event.active) {
          simulation.alphaTarget(0)
        }
        if (!pinnedNodes.has(d.id)) {
          d.fx = null
          d.fy = null
        }
      }))
      .on('click', (event, d) => { event.stopPropagation(); onNodeClickRef.current?.(d) })
      .on('dblclick', (event, d) => {
        // Stop propagation so d3-zoom's default dblclick-to-zoom does not fire
        // when the user double-clicks a node to expand it.
        event.preventDefault()
        event.stopPropagation()
        onNodeDoubleClickRef.current?.(d)
      })
      .on('contextmenu', (event, d) => { event.preventDefault(); onNodeRightClickRef.current?.(d, event) })
      .on('keydown', (event: KeyboardEvent, d: GraphNode) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          event.stopPropagation()
          onNodeClickRef.current?.(d)
        }
      })

    const labels = container.append('g').attr('class', 'labels').selectAll('text').data(filteredNodes).enter().append('text')
      .text((d) => getNodeCaption(d, nodeStyles)).attr('font-size', '12px').attr('dx', (d) => getNodeStyle(d, nodeStyles).size + 5).attr('dy', 4).style('pointer-events', 'none').style('fill', '#e4e4e7')

    const edgeLabels = container.append('g').attr('class', 'edge-labels').selectAll('text').data(filteredEdges).enter().append('text')
      .text((d) => getEdgeCaption(d, edgeStyles, edgeWidthScale, edgeWidthMapping.property)).attr('font-size', '10px').attr('text-anchor', 'middle').attr('dy', -4).style('pointer-events', 'none').style('fill', '#a1a1aa')

    const centerX = viewportWidth / 2, centerY = viewportHeight / 2
    const fitToView = (animate = true) => {
      if (!nodesWithPositions.length) return
      const xs = nodesWithPositions.map((n) => n.x ?? centerX), ys = nodesWithPositions.map((n) => n.y ?? centerY)
      const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
      const contentWidth = maxX - minX || 1, contentHeight = maxY - minY || 1
      const margin = layout === 'force' ? 20 : 40
      const scale = Math.max(0.1, 0.92 * Math.min((viewportWidth - 2 * margin) / contentWidth, (viewportHeight - 2 * margin) / contentHeight))
      setDebugFitScale(scale)
      const transform = d3.zoomIdentity.translate(centerX - scale * (minX + contentWidth / 2), centerY - scale * (minY + contentHeight / 2)).scale(scale)
      applyingAutoTransformRef.current = true
      if (animate) svg.transition().duration(400).on('end', () => applyingAutoTransformRef.current = false).call(zoom.transform, transform)
      else { svg.call(zoom.transform, transform); applyingAutoTransformRef.current = false }
    }
    fitToViewRef.current = () => fitToView(true)

    const nodeById = new Map(nodesWithPositions.map((n) => [n.id, n]))
    const getNode = (endpoint: string | GraphNode) => typeof endpoint === 'string' ? nodeById.get(endpoint) : endpoint

    let didAutoStop = false
    const pathByEdgeId = new Map<string, LinkPathResult>()
    function applyPositions() {
      if (layout === 'force' && hasEdges && !didAutoStop && simulation.alpha() < 0.035) { didAutoStop = true; simulation.stop() }
      pathByEdgeId.clear()
      if (hasEdges) {
        for (const e of filteredEdges) {
          pathByEdgeId.set(e.id, linkPath(e, getNode, getNodeR, parallelByEdgeId.get(e.id)))
        }
      }
      applyLinkPathD(link, pathByEdgeId)
      applyLinkPathD(linkHit, pathByEdgeId)
      node.attr('cx', (d) => d.x ?? centerX).attr('cy', (d) => d.y ?? centerY)
      labels.attr('x', (d) => d.x ?? centerX).attr('y', (d) => d.y ?? centerY)
      edgeLabels
        .attr('x', (d) => pathByEdgeId.get(d.id)?.lx ?? centerX)
        .attr('y', (d) => pathByEdgeId.get(d.id)?.ly ?? centerY)
    }
    simulation.on('tick', applyPositions)
    applyPositions()
    if (layout !== 'force' || !hasEdges) simulation.tick()
    if (userZoomedRef.current) { applyingAutoTransformRef.current = true; svg.call(zoom.transform, zoomTransformRef.current); applyingAutoTransformRef.current = false }
    else fitToView(false)

    return () => {
      fitToViewRef.current = null;
      simulation.stop();
      // Explicitly release references
      simulation.nodes([]);
      if (hasEdges) {
        const linkForce = simulation.force('link');
        // d3-force's typed return for `force('link')` is the union of every
        // registered force; narrowing requires a runtime guard plus a generic
        // we'd have to re-derive — `as any` here is the standard pattern in
        // the d3-force community for this exact teardown.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if (linkForce && 'links' in linkForce) (linkForce as any).links([]);
      }
      // Remove all elements and event listeners
      svg.on('.zoom', null);
      svg.selectAll('*').remove();
    }
  }, [filteredNodes, filteredEdges, pathNodeIds, pathEdgeIds, width, height, layout, nodeStyles, edgeStyles, selectedNode, pinnedNodes, edgeWidthScale, edgeWidthMapping.property])

  // ROADMAP A11 phase 2 — camera focus on newly-added neighbourhood. Runs
  // *after* the main mount effect (which always re-fits the whole canvas
  // when the data changes), and overrides that fit by zooming into just
  // the anchor union {clicked node ∪ added neighbours}. We defer one frame
  // so the simulation has had a chance to seed positions for the new
  // nodes — without it the bounds would be zero-area and the zoom would
  // explode to scaleExtent's upper bound.
  useEffect(() => {
    if (cameraFocusAnchorIds.length === 0) return
    const sim = simulationRef.current
    const svg = svgSelectionRef.current
    const zoom = zoomBehaviorRef.current
    if (!sim || !svg || !zoom) return

    const anchorSet = new Set(cameraFocusAnchorIds)
    // The first anchor is, by contract from
    // `WorkspacePage.handleDoubleClickNode`, the actually-clicked node id
    // (`[node.id, ...merged.addedNodeIds]`). `anchors` below is the
    // simulation-ordered subset, so we must look the clicked node up by
    // id rather than trusting `anchors[0]` — otherwise the temporary pin
    // can anchor the layout around an arbitrary neighbour.
    const clickedId = cameraFocusAnchorIds[0]

    // Cancel any in-flight pin from a prior camera-focus pass before we
    // schedule a new one. Release the previously-pinned node's fx/fy
    // unless the user has explicitly pinned it via `pinnedNodes`.
    const releasePin = () => {
      if (pinRef.current.timer) {
        clearTimeout(pinRef.current.timer)
      }
      const prevId = pinRef.current.id
      if (prevId && !pinnedNodes.has(prevId)) {
        const prevNode = sim.nodes().find((n) => n.id === prevId)
        if (prevNode) {
          prevNode.fx = null
          prevNode.fy = null
        }
      }
      pinRef.current = { timer: null, id: null }
    }

    const raf = requestAnimationFrame(() => {
      const allNodes = sim.nodes()
      const anchors = allNodes.filter((n) => anchorSet.has(n.id))
      if (anchors.length === 0) {
        clearCameraFocusAnchorIds()
        return
      }

      const xs = anchors.map((n) => n.x ?? 0)
      const ys = anchors.map((n) => n.y ?? 0)
      const minX = Math.min(...xs)
      const maxX = Math.max(...xs)
      const minY = Math.min(...ys)
      const maxY = Math.max(...ys)
      // Single-anchor / tightly-clustered anchors collapse to a zero-area
      // bounding box. Floor the content size at 200px so the zoom lands at
      // a usable detail level (rather than scaleExtent's max of 20).
      const contentW = Math.max(maxX - minX, 200)
      const contentH = Math.max(maxY - minY, 200)
      const margin = 60
      const fitScale = 0.92 * Math.min(
        (resolvedSize.width - 2 * margin) / contentW,
        (resolvedSize.height - 2 * margin) / contentH,
      )
      const scale = Math.max(0.3, Math.min(2, fitScale))
      const cx = (minX + maxX) / 2
      const cy = (minY + maxY) / 2
      const transform = d3.zoomIdentity
        .translate(resolvedSize.width / 2 - scale * cx, resolvedSize.height / 2 - scale * cy)
        .scale(scale)

      applyingAutoTransformRef.current = true
      // Mark as "user zoom" so the next simulation tick / re-fit doesn't
      // immediately reset us back to the whole-canvas bounds.
      userZoomedRef.current = true
      // Both `'end'` (normal completion) and `'interrupt'` (user pan/zoom
      // or another transform during the 400 ms window) must clear the
      // auto-transform flag and the focus anchors — otherwise an
      // interrupted transition leaves `applyingAutoTransformRef` stuck
      // `true` and `cameraFocusAnchorIds` non-empty, breaking subsequent
      // user-zoom classification.
      const finishAutoFocus = () => {
        applyingAutoTransformRef.current = false
        clearCameraFocusAnchorIds()
        // An interrupt before the 2 s pin release should also flush the
        // pin so we don't leave a node fixed indefinitely.
        releasePin()
      }
      svg
        .transition()
        .duration(400)
        .on('end', finishAutoFocus)
        .on('interrupt', finishAutoFocus)
        .call(zoom.transform, transform)

      // Briefly pin the clicked node so the force layout settles around
      // the focus rather than drifting it back to the centre.
      const clicked = allNodes.find((n) => n.id === clickedId) ?? anchors[0]
      if (clicked && layout === 'force') {
        // Replace any prior pin first (covers rapid successive expands).
        releasePin()
        clicked.fx = clicked.x ?? 0
        clicked.fy = clicked.y ?? 0
        sim.alphaTarget(0.1).restart()
        const clickedIdForRelease = clicked.id
        const timer = setTimeout(() => {
          // Honour an explicit pin from `pinnedNodes` — don't release a node
          // the user has separately decided should stay put.
          if (!pinnedNodes.has(clickedIdForRelease)) {
            clicked.fx = null
            clicked.fy = null
          }
          sim.alphaTarget(0)
          pinRef.current = { timer: null, id: null }
        }, 2000)
        pinRef.current = { timer, id: clickedIdForRelease }
      }
    })

    // NOTE: the cleanup intentionally does *not* clear the pin timer.
    // The transition's `on('end')` handler calls `clearCameraFocusAnchorIds`
    // ~t≈416 ms, which mutates the store and causes React to re-run this
    // effect — if we cleared the pin timer here, the still-pending 2 s
    // release would be cancelled and the node would stay fixed forever.
    // Pin lifetime is owned by `pinRef` and cleaned up by `releasePin`
    // (called from `finishAutoFocus`, the next focus pass, or unmount).
    return () => {
      cancelAnimationFrame(raf)
    }
    // `filteredNodes` is in deps so the effect re-runs after the main mount
    // effect has rebuilt the simulation with the new data — without it the
    // first focus after an expand reads stale positions.
  }, [cameraFocusAnchorIds, filteredNodes, layout, resolvedSize.width, resolvedSize.height, pinnedNodes, clearCameraFocusAnchorIds])

  // Unmount-only scrub: if the component tears down while a pin is still
  // active (e.g. tab close mid-focus), release fx/fy so a future remount
  // doesn't inherit a stuck pin via mutated simulation node references.
  useEffect(() => {
    return () => {
      if (pinRef.current.timer) {
        clearTimeout(pinRef.current.timer)
      }
      const sim = simulationRef.current
      const id = pinRef.current.id
      if (sim && id) {
        const n = sim.nodes().find((n) => n.id === id)
        if (n) {
          n.fx = null
          n.fy = null
        }
      }
      pinRef.current = { timer: null, id: null }
    }
  }, [])

  const zoomBy = (factor: number) => {
    const svg = svgSelectionRef.current, zoom = zoomBehaviorRef.current
    if (!svg || !zoom) return
    const el = svg.node()
    if (!el) return
    const current = d3.zoomTransform(el), nextScale = Math.max(0.05, Math.min(20, current.k * factor))
    svg.call(zoom.scaleTo, nextScale, [resolvedSize.width / 2, resolvedSize.height / 2])
  }

  if (canvasMode) {
    return (
      <div className="w-full h-full bg-zinc-950 relative">
        <div
          className="absolute left-2 top-2 z-10 pointer-events-none rounded border border-zinc-600/60 bg-zinc-800/70 px-2 py-0.5 text-[10px] text-zinc-400 font-mono"
          title="Canvas renderer active for performance"
        >
          Canvas mode
        </div>
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          width={width}
          height={height}
          pathHighlights={pathHighlights}
          onNodeClick={onNodeClick}
          onNodeDoubleClick={onNodeDoubleClick}
          onNodeRightClick={onNodeRightClick}
          onEdgeClick={onEdgeClick}
          onExportReady={onExportReady}
        />
      </div>
    )
  }

  return (
    <div className="w-full h-full bg-zinc-950 relative">
      {import.meta.env.DEV && (
        <div className="absolute left-2 top-2 z-10 pointer-events-none rounded bg-emerald-500/20 border border-emerald-400/40 px-2 py-1 text-[10px] text-emerald-300 font-mono">
          GraphView marker: 2026-04-21-c2-v4 | prop:{width}x{height} | view:{resolvedSize.width}x{resolvedSize.height} | fit:{debugFitScale?.toFixed(2) ?? 'n/a'}
        </div>
      )}
      <div className="absolute right-3 bottom-3 z-20 flex items-center gap-1 rounded border border-zinc-700 bg-zinc-900/85 p-1">
        <button type="button" onClick={() => zoomBy(1.2)} className="h-8 w-8 rounded bg-zinc-800 text-zinc-200 hover:bg-zinc-700" aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" onClick={() => zoomBy(0.8)} className="h-8 w-8 rounded bg-zinc-800 text-zinc-200 hover:bg-zinc-700" aria-label="Zoom out" title="Zoom out">-</button>
        <button type="button" onClick={() => fitToViewRef.current?.()} className="h-8 rounded bg-zinc-800 px-2 text-xs font-medium text-zinc-200 hover:bg-zinc-700" aria-label="Reset zoom" title="Reset zoom">Reset</button>
      </div>
      <svg ref={svgRef} width={resolvedSize.width} height={resolvedSize.height} className="block" />
    </div>
  )
}
