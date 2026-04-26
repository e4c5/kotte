/**
 * Canvas 2D renderer for large graphs (C2.4).
 * Activated by GraphView when node+edge count exceeds CANVAS_THRESHOLD_ENTER.
 * Shares the same props, store subscriptions, and linkPath geometry as the SVG path.
 */

import { useEffect, useRef, useMemo, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { useGraphStore } from '../stores/graphStore'
import { initializeLayout } from '../utils/graphLayouts'
import { getNodeStyle, getEdgeStyle, getNodeCaption, getEdgeCaption } from '../utils/graphStyles'
import { linkPath, parallelEdgeMeta, type LinkPathResult } from '../utils/graphLinkPaths'
import type { GraphNode, GraphEdge, PathHighlights } from './GraphView'
import GraphMinimap from './GraphMinimap'
import LassoActionBar from './LassoActionBar'

// ── geometry helpers ──────────────────────────────────────────────────────────

interface Tip {
  x: number
  y: number
  angle: number
}

/**
 * Extract arrowhead tip and tangent angle from a linkPath `d` string.
 * All linkPath paths end with a quadratic bezier "Q cx cy x1 y1".
 */
function parseTip(d: string): Tip | null {
  const q = d.match(/Q\s*([-\d.e]+)\s+([-\d.e]+)\s+([-\d.e]+)\s+([-\d.e]+)\s*$/)
  if (q) {
    const cx = +q[1], cy = +q[2], x1 = +q[3], y1 = +q[4]
    return { x: x1, y: y1, angle: Math.atan2(y1 - cy, x1 - cx) }
  }
  // Degenerate near-zero line: "M x0 y0 L x1 y1"
  const l = d.match(/M\s*([-\d.e]+)\s+([-\d.e]+).*L\s*([-\d.e]+)\s+([-\d.e]+)\s*$/)
  if (l) {
    const x0 = +l[1], y0 = +l[2], x1 = +l[3], y1 = +l[4]
    return { x: x1, y: y1, angle: Math.atan2(y1 - y0, x1 - x0) }
  }
  return null
}

function drawArrow(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  angle: number,
  size: number,
) {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo(-size, -size * 0.4)
  ctx.lineTo(-size, size * 0.4)
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}

// ── types ──────────────────────────────────────────────────────────────────────

interface Transform {
  x: number
  y: number
  k: number
}

interface IdleState {
  type: 'idle'
}
interface PanState {
  type: 'pan'
  startX: number
  startY: number
  startTx: number
  startTy: number
}
interface DragState {
  type: 'drag'
  node: GraphNode
  didMove: boolean
}
interface LassoState {
  type: 'lasso'
  x0: number
  y0: number
  x1: number
  y1: number
}
type PointerState = IdleState | PanState | DragState | LassoState

const ZOOM_MIN = 0.05
const ZOOM_MAX = 20
const ARROW_SIZE = 8

export interface GraphCanvasProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  width: number
  height: number
  pathHighlights?: PathHighlights
  onNodeClick?: (node: GraphNode) => void
  onNodeDoubleClick?: (node: GraphNode) => void
  onNodeRightClick?: (node: GraphNode, event: MouseEvent) => void
  onEdgeClick?: (edge: GraphEdge) => void
  onExportReady?: (exportFn: () => Promise<void>) => void
}

// ── component ─────────────────────────────────────────────────────────────────

export default function GraphCanvas({
  nodes,
  edges,
  width,
  height,
  pathHighlights,
  onNodeClick,
  onNodeDoubleClick,
  onNodeRightClick,
  onEdgeClick,
  onExportReady,
}: GraphCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const simRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null)
  const transformRef = useRef<Transform>({ x: 0, y: 0, k: 1 })
  const dirtyRef = useRef(true)
  const pathByEdgeIdRef = useRef(new Map<string, LinkPathResult>())
  // drawRef holds the latest draw closure; the RAF loop always calls the current version.
  const drawRef = useRef<(() => void) | null>(null)
  const [resolvedSize, setResolvedSize] = useState({ width, height })

  // Stable callback refs so event handlers never go stale.
  const onNodeClickRef = useRef(onNodeClick)
  const onNodeDoubleClickRef = useRef(onNodeDoubleClick)
  const onNodeRightClickRef = useRef(onNodeRightClick)
  const onEdgeClickRef = useRef(onEdgeClick)
  useEffect(() => {
    onNodeClickRef.current = onNodeClick
    onNodeDoubleClickRef.current = onNodeDoubleClick
    onNodeRightClickRef.current = onNodeRightClick
    onEdgeClickRef.current = onEdgeClick
  }, [onNodeClick, onNodeDoubleClick, onNodeRightClick, onEdgeClick])

  const {
    layout,
    nodeStyles,
    edgeStyles,
    edgeWidthMapping,
    filters,
    selectedNode,
    pinnedNodes,
    hiddenNodes,
    lassoNodes,
    cameraFocusAnchorIds,
    clearCameraFocusAnchorIds,
  } = useGraphStore()

  // Trigger redraw whenever lasso selection changes.
  useEffect(() => {
    dirtyRef.current = true
  }, [lassoNodes])

  // Mirror the same filter logic from GraphView.
  const filteredNodes = useMemo(() => {
    let filtered = nodes.filter((n) => !hiddenNodes.has(n.id))
    if (filters.nodeLabels.size > 0)
      filtered = filtered.filter((n) => filters.nodeLabels.has(n.label))
    if (filters.propertyFilters.length > 0) {
      filtered = filtered.filter((node) =>
        filters.propertyFilters.every((f) => {
          if (f.label && f.label !== node.label) return true
          const pv = String(node.properties[f.property] || '')
          const fv = f.value.toLowerCase()
          switch (f.operator) {
            case 'equals': return pv.toLowerCase() === fv
            case 'contains': return pv.toLowerCase().includes(fv)
            case 'startsWith': return pv.toLowerCase().startsWith(fv)
            case 'endsWith': return pv.toLowerCase().endsWith(fv)
            default: return true
          }
        }),
      )
    }
    return filtered
  }, [nodes, filters, hiddenNodes])

  const filteredEdges = useMemo(() => {
    let filtered = edges.filter((e) => {
      const sid = typeof e.source === 'string' ? e.source : e.source.id
      const tid = typeof e.target === 'string' ? e.target : e.target.id
      return !hiddenNodes.has(sid) && !hiddenNodes.has(tid)
    })
    if (filters.edgeLabels.size > 0)
      filtered = filtered.filter((e) => filters.edgeLabels.has(e.label))
    const visIds = new Set(filteredNodes.map((n) => n.id))
    return filtered.filter((e) => {
      const sid = typeof e.source === 'string' ? e.source : e.source.id
      const tid = typeof e.target === 'string' ? e.target : e.target.id
      return visIds.has(sid) && visIds.has(tid)
    })
  }, [edges, filters, hiddenNodes, filteredNodes])

  const pathNodeIds = useMemo(
    () => new Set(pathHighlights?.nodeIds?.map(String) ?? []),
    [pathHighlights?.nodeIds],
  )
  const pathEdgeIds = useMemo(
    () => new Set(pathHighlights?.edgeIds?.map(String) ?? []),
    [pathHighlights?.edgeIds],
  )

  const edgeWidthScale = useMemo(() => {
    if (!edgeWidthMapping.enabled || !edgeWidthMapping.property) return null
    const vals = filteredEdges
      .map((e) => {
        const v = e.properties[edgeWidthMapping.property!]
        if (v == null) return null
        const n = typeof v === 'number' ? v : parseFloat(String(v))
        return isNaN(n) ? null : n
      })
      .filter((v): v is number => v !== null)
    if (!vals.length) return null
    const mn = Math.min(...vals), mx = Math.max(...vals)
    return edgeWidthMapping.scaleType === 'log' && mn > 0
      ? d3.scaleLog().domain([mn, mx]).range([edgeWidthMapping.minWidth, edgeWidthMapping.maxWidth])
      : d3
          .scaleLinear()
          .domain([mn, mx])
          .range([edgeWidthMapping.minWidth, edgeWidthMapping.maxWidth])
  }, [filteredEdges, edgeWidthMapping])

  // ── RAF loop — runs once, always calls the latest drawRef ────────────────────
  useEffect(() => {
    let rafId: number
    function loop() {
      if (dirtyRef.current && drawRef.current) {
        drawRef.current()
        dirtyRef.current = false
      }
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [])

  // ── canvas export ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!onExportReady) return
    const exportFn = async () => {
      const canvas = canvasRef.current
      if (!canvas) return
      await new Promise<void>((resolve) => {
        canvas.toBlob((blob) => {
          if (!blob) {
            resolve()
            return
          }
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `graph-export-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`
          document.body.appendChild(a)
          a.click()
          a.remove()
          queueMicrotask(() => URL.revokeObjectURL(url))
          resolve()
        }, 'image/png')
      })
    }
    onExportReady(exportFn)
  }, [onExportReady])

  // ── main effect: simulation + draw closure + event handlers ──────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const containerRect = canvas.parentElement?.getBoundingClientRect()
    const vw = Math.max(Math.floor(containerRect?.width ?? width), 1)
    const vh = Math.max(Math.floor(containerRect?.height ?? height), 1)
    setResolvedSize((prev) =>
      prev.width === vw && prev.height === vh ? prev : { width: vw, height: vh },
    )

    // HiDPI: size the backing store at physical pixels.
    const dpr = window.devicePixelRatio || 1
    canvas.width = vw * dpr
    canvas.height = vh * dpr
    canvas.style.width = `${vw}px`
    canvas.style.height = `${vh}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // ── simulation setup ────────────────────────────────────────────────────────
    // initializeLayout mutates nodes in-place; filteredNodes and the returned array
    // are the same objects — d3-force's x/y updates are visible to draw().
    initializeLayout(filteredNodes, layout, vw, vh)
    const nodesArr = filteredNodes
    if (!nodesArr.length) {
      drawRef.current = null
      return
    }

    const hasEdges = filteredEdges.length > 0
    let sim: d3.Simulation<GraphNode, GraphEdge>
    if (layout === 'force' && hasEdges) {
      sim = d3
        .forceSimulation<GraphNode>(nodesArr)
        .alpha(1)
        .alphaDecay(0.05)
        .velocityDecay(0.45)
        .force(
          'link',
          d3.forceLink<GraphNode, GraphEdge>(filteredEdges).id((d) => d.id).distance(90),
        )
        .force('charge', d3.forceManyBody().strength(-110))
        .force('center', d3.forceCenter(vw / 2, vh / 2))
        .force('x', d3.forceX(vw / 2).strength(0.04))
        .force('y', d3.forceY(vh / 2).strength(0.04))
        .force('collision', d3.forceCollide().radius(28))
    } else {
      sim = d3.forceSimulation<GraphNode>(nodesArr).alpha(0).stop()
    }

    nodesArr.forEach((n) => {
      if (pinnedNodes.has(n.id)) {
        n.fx = n.x ?? vw / 2
        n.fy = n.y ?? vh / 2
      }
    })
    simRef.current = sim

    const nodeById = new Map(nodesArr.map((n) => [n.id, n]))
    const getNode = (ep: string | GraphNode) => (typeof ep === 'string' ? nodeById.get(ep) : ep)
    const getNodeR = (n: GraphNode) => getNodeStyle(n, nodeStyles).size
    const parallelByEdgeId = parallelEdgeMeta(filteredEdges)

    function rebuildPaths() {
      pathByEdgeIdRef.current.clear()
      for (const e of filteredEdges) {
        pathByEdgeIdRef.current.set(
          e.id,
          linkPath(e, getNode, getNodeR, parallelByEdgeId.get(e.id)),
        )
      }
    }

    // ── fit-to-view ─────────────────────────────────────────────────────────────
    function computeFitTransform(): Transform {
      const cx = vw / 2, cy = vh / 2
      const xs = nodesArr.map((n) => n.x ?? cx)
      const ys = nodesArr.map((n) => n.y ?? cy)
      const mnX = Math.min(...xs), mxX = Math.max(...xs)
      const mnY = Math.min(...ys), mxY = Math.max(...ys)
      const cw = mxX - mnX || 1, ch = mxY - mnY || 1
      const margin = layout === 'force' ? 20 : 40
      const k = Math.max(0.1, 0.92 * Math.min((vw - 2 * margin) / cw, (vh - 2 * margin) / ch))
      return { k, x: cx - k * (mnX + cw / 2), y: cy - k * (mnY + ch / 2) }
    }

    transformRef.current = computeFitTransform()
    rebuildPaths()
    dirtyRef.current = true

    // ── draw closure ─────────────────────────────────────────────────────────────
    function draw() {
      // ctx is guaranteed non-null here — closures are only active while the canvas is mounted.
      if (!ctx) return
      const { x: tx, y: ty, k } = transformRef.current

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, vw, vh)
      ctx.fillStyle = '#09090b'
      ctx.fillRect(0, 0, vw, vh)

      ctx.translate(tx, ty)
      ctx.scale(k, k)

      const edgeColor = (e: GraphEdge) =>
        pathEdgeIds.has(String(e.id))
          ? '#0066cc'
          : getEdgeStyle(e, edgeStyles, edgeWidthScale, edgeWidthMapping.property).color

      // Edges
      for (const edge of filteredEdges) {
        const result = pathByEdgeIdRef.current.get(edge.id)
        if (!result) continue
        const color = edgeColor(edge)
        const style = getEdgeStyle(edge, edgeStyles, edgeWidthScale, edgeWidthMapping.property)
        const sw = pathEdgeIds.has(String(edge.id)) ? Math.max(3, style.size) : style.size
        const alpha = pathEdgeIds.has(String(edge.id)) ? 1 : 0.6

        ctx.globalAlpha = alpha
        ctx.strokeStyle = color
        ctx.lineWidth = sw
        ctx.stroke(new Path2D(result.d))

        const tip = parseTip(result.d)
        if (tip) {
          ctx.fillStyle = color
          drawArrow(ctx, tip.x, tip.y, tip.angle, ARROW_SIZE)
        }

        const caption = getEdgeCaption(edge, edgeStyles, edgeWidthScale, edgeWidthMapping.property)
        if (caption) {
          ctx.globalAlpha = 0.7
          ctx.fillStyle = '#a1a1aa'
          ctx.font = '10px sans-serif'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'alphabetic'
          ctx.fillText(caption, result.lx, result.ly - 4)
        }
      }

      ctx.globalAlpha = 1

      // Nodes
      for (const node of filteredNodes) {
        const style = getNodeStyle(node, nodeStyles)
        const nx = node.x ?? vw / 2
        const ny = node.y ?? vh / 2
        const fill = pathNodeIds.has(node.id) ? '#0066cc' : style.color
        const stroke =
          selectedNode === node.id
            ? '#ff0000'
            : pathNodeIds.has(node.id)
              ? '#004499'
              : pinnedNodes.has(node.id)
                ? '#f59e0b'
                : '#fff'
        const sw =
          selectedNode === node.id || pathNodeIds.has(node.id) || pinnedNodes.has(node.id) ? 3 : 2

        ctx.beginPath()
        ctx.arc(nx, ny, style.size, 0, Math.PI * 2)
        ctx.fillStyle = fill
        ctx.fill()
        ctx.strokeStyle = stroke
        ctx.lineWidth = sw
        ctx.stroke()

        const caption = getNodeCaption(node, nodeStyles)
        if (caption) {
          ctx.fillStyle = '#e4e4e7'
          ctx.font = '12px sans-serif'
          ctx.textAlign = 'left'
          ctx.textBaseline = 'middle'
          ctx.fillText(caption, nx + style.size + 5, ny)
        }
      }

      ctx.globalAlpha = 1

      // Lasso rings — dashed outline around each lasso-selected node (world space)
      const lasso = useGraphStore.getState().lassoNodes
      if (lasso.size > 0) {
        ctx.setLineDash([4, 3])
        ctx.lineWidth = 2
        ctx.strokeStyle = '#60a5fa'
        for (const node of filteredNodes) {
          if (!lasso.has(node.id)) continue
          const style = getNodeStyle(node, nodeStyles)
          ctx.beginPath()
          ctx.arc(node.x ?? vw / 2, node.y ?? vh / 2, style.size + 5, 0, Math.PI * 2)
          ctx.stroke()
        }
        ctx.setLineDash([])
      }

      // Lasso drag rect — drawn in screen space after resetting transform
      if (pointerState.type === 'lasso') {
        const { x0, y0, x1, y1 } = pointerState
        const rx = Math.min(x0, x1), ry = Math.min(y0, y1)
        const rw = Math.abs(x1 - x0), rh = Math.abs(y1 - y0)
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
        ctx.fillStyle = 'rgba(96,165,250,0.08)'
        ctx.fillRect(rx, ry, rw, rh)
        ctx.strokeStyle = '#60a5fa'
        ctx.lineWidth = 1
        ctx.setLineDash([4, 2])
        ctx.strokeRect(rx, ry, rw, rh)
        ctx.setLineDash([])
      }
    }

    drawRef.current = draw

    let autoStopped = false
    sim.on('tick', () => {
      if (!autoStopped && sim.alpha() < 0.035) {
        autoStopped = true
        sim.stop()
      }
      rebuildPaths()
      dirtyRef.current = true
    })

    if (layout !== 'force' || !hasEdges) sim.tick()

    // ── pointer / wheel event handling ──────────────────────────────────────────
    function toWorld(sx: number, sy: number): [number, number] {
      const { x: tx, y: ty, k } = transformRef.current
      return [(sx - tx) / k, (sy - ty) / k]
    }

    function hitNode(wx: number, wy: number): GraphNode | null {
      for (let i = nodesArr.length - 1; i >= 0; i--) {
        const n = nodesArr[i]
        const r = getNodeStyle(n, nodeStyles).size
        if (Math.hypot((n.x ?? 0) - wx, (n.y ?? 0) - wy) <= r) return n
      }
      return null
    }

    function hitEdge(wx: number, wy: number): GraphEdge | null {
      if (!onEdgeClickRef.current || !ctx) return null
      const { x: tx, y: ty, k } = transformRef.current
      ctx.save()
      ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * tx, dpr * ty)
      ctx.lineWidth = 16 / k
      let found: GraphEdge | null = null
      for (let i = filteredEdges.length - 1; i >= 0; i--) {
        const e = filteredEdges[i]
        const pr = pathByEdgeIdRef.current.get(e.id)
        if (!pr) continue
        if (ctx.isPointInStroke(new Path2D(pr.d), wx, wy)) {
          found = e
          break
        }
      }
      ctx.restore()
      return found
    }

    // Event handlers close over `canvas` which is guaranteed non-null at registration time.
    // TypeScript can't narrow const captures in closures; `!` is intentional here.
    const el = canvas

    let pointerState: PointerState = { type: 'idle' }
    let lastClick: { id: string; time: number } | null = null

    function onWheel(e: WheelEvent) {
      e.preventDefault()
      const { x: tx, y: ty, k } = transformRef.current
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
      const nk = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, k * factor))
      const mx = e.offsetX, my = e.offsetY
      transformRef.current = { k: nk, x: mx - (mx - tx) * (nk / k), y: my - (my - ty) * (nk / k) }
      dirtyRef.current = true
    }

    function onPointerDown(e: PointerEvent) {
      if (e.button !== 0) return
      el.setPointerCapture(e.pointerId)
      const [wx, wy] = toWorld(e.offsetX, e.offsetY)
      const hn = hitNode(wx, wy)
      if (e.shiftKey && !hn) {
        pointerState = { type: 'lasso', x0: e.offsetX, y0: e.offsetY, x1: e.offsetX, y1: e.offsetY }
        el.style.cursor = 'crosshair'
      } else if (hn) {
        pointerState = { type: 'drag', node: hn, didMove: false }
        el.style.cursor = 'grabbing'
        if (layout === 'force') {
          sim.alphaTarget(0.3).restart()
          hn.fx = hn.x ?? 0
          hn.fy = hn.y ?? 0
        }
      } else {
        const { x: tx, y: ty } = transformRef.current
        pointerState = { type: 'pan', startX: e.offsetX, startY: e.offsetY, startTx: tx, startTy: ty }
        el.style.cursor = 'grabbing'
      }
    }

    function onPointerMove(e: PointerEvent) {
      if (pointerState.type === 'lasso') {
        pointerState = { ...pointerState, x1: e.offsetX, y1: e.offsetY }
        dirtyRef.current = true
      } else if (pointerState.type === 'pan') {
        const dx = e.offsetX - pointerState.startX
        const dy = e.offsetY - pointerState.startY
        transformRef.current = { ...transformRef.current, x: pointerState.startTx + dx, y: pointerState.startTy + dy }
        dirtyRef.current = true
      } else if (pointerState.type === 'drag') {
        const [wx, wy] = toWorld(e.offsetX, e.offsetY)
        pointerState = { ...pointerState, didMove: true }
        if (layout === 'force') {
          pointerState.node.fx = wx
          pointerState.node.fy = wy
        } else {
          pointerState.node.x = wx
          pointerState.node.y = wy
          rebuildPaths()
          dirtyRef.current = true
        }
      }
    }

    function onPointerUp(e: PointerEvent) {
      if (e.button !== 0) return
      el.style.cursor = 'grab'
      if (pointerState.type === 'lasso') {
        const { x0, y0, x1, y1 } = pointerState
        const { x: tx, y: ty, k } = transformRef.current
        const sx0 = Math.min(x0, x1), sy0 = Math.min(y0, y1)
        const sx1 = Math.max(x0, x1), sy1 = Math.max(y0, y1)
        const wx0 = (sx0 - tx) / k, wy0 = (sy0 - ty) / k
        const wx1 = (sx1 - tx) / k, wy1 = (sy1 - ty) / k
        const hitSet = new Set<string>()
        for (const n of nodesArr) {
          const nx = n.x ?? 0, ny = n.y ?? 0
          if (nx >= wx0 && nx <= wx1 && ny >= wy0 && ny <= wy1) hitSet.add(n.id)
        }
        useGraphStore.getState().setLassoNodes(hitSet)
        pointerState = { type: 'idle' }
        dirtyRef.current = true
      } else if (pointerState.type === 'drag') {
        const { node, didMove } = pointerState
        if (!didMove) {
          const now = Date.now()
          if (lastClick && lastClick.id === node.id && now - lastClick.time < 300) {
            onNodeDoubleClickRef.current?.(node)
            lastClick = null
          } else {
            onNodeClickRef.current?.(node)
            lastClick = { id: node.id, time: now }
          }
        }
        if (layout === 'force') {
          if (!pinnedNodes.has(node.id)) {
            node.fx = null
            node.fy = null
          }
          sim.alphaTarget(0)
        }
      } else if (pointerState.type === 'pan') {
        const dx = e.offsetX - pointerState.startX
        const dy = e.offsetY - pointerState.startY
        if (Math.hypot(dx, dy) < 5) {
          const [wx, wy] = toWorld(e.offsetX, e.offsetY)
          const he = hitEdge(wx, wy)
          if (he) onEdgeClickRef.current?.(he)
          else useGraphStore.getState().clearLassoNodes()
        }
      }
      pointerState = { type: 'idle' }
    }

    function onContextMenu(e: MouseEvent) {
      e.preventDefault()
      const [wx, wy] = toWorld(e.offsetX, e.offsetY)
      const hn = hitNode(wx, wy)
      if (hn) onNodeRightClickRef.current?.(hn, e)
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') useGraphStore.getState().clearLassoNodes()
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('pointerdown', onPointerDown)
    el.addEventListener('pointermove', onPointerMove)
    el.addEventListener('pointerup', onPointerUp)
    el.addEventListener('contextmenu', onContextMenu)
    window.addEventListener('keydown', onKeyDown)

    return () => {
      sim.stop()
      sim.nodes([])
      if (hasEdges) {
        const lf = sim.force('link')
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if (lf && 'links' in lf) (lf as any).links([])
      }
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('pointerdown', onPointerDown)
      el.removeEventListener('pointermove', onPointerMove)
      el.removeEventListener('pointerup', onPointerUp)
      el.removeEventListener('contextmenu', onContextMenu)
      window.removeEventListener('keydown', onKeyDown)
      drawRef.current = null
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
    edgeWidthScale,
    edgeWidthMapping.property,
  ])

  // ── camera focus (mirrors GraphView's cameraFocusAnchorIds logic) ─────────────
  useEffect(() => {
    if (!cameraFocusAnchorIds.length) return
    const sim = simRef.current
    if (!sim) return

    const anchorSet = new Set(cameraFocusAnchorIds)
    const raf = requestAnimationFrame(() => {
      const anchors = sim.nodes().filter((n) => anchorSet.has(n.id))
      if (!anchors.length) {
        clearCameraFocusAnchorIds()
        return
      }
      const xs = anchors.map((n) => n.x ?? 0)
      const ys = anchors.map((n) => n.y ?? 0)
      const mnX = Math.min(...xs), mxX = Math.max(...xs)
      const mnY = Math.min(...ys), mxY = Math.max(...ys)
      const cw = Math.max(mxX - mnX, 200), ch = Math.max(mxY - mnY, 200)
      const margin = 60
      const fitK = 0.92 * Math.min(
        (resolvedSize.width - 2 * margin) / cw,
        (resolvedSize.height - 2 * margin) / ch,
      )
      const k = Math.max(0.3, Math.min(2, fitK))
      const cx = (mnX + mxX) / 2, cy = (mnY + mxY) / 2
      const target: Transform = {
        k,
        x: resolvedSize.width / 2 - k * cx,
        y: resolvedSize.height / 2 - k * cy,
      }
      const start = { ...transformRef.current }
      const t0 = performance.now()
      const duration = 400

      function step() {
        const t = Math.min((performance.now() - t0) / duration, 1)
        const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t
        transformRef.current = {
          k: start.k + (target.k - start.k) * ease,
          x: start.x + (target.x - start.x) * ease,
          y: start.y + (target.y - start.y) * ease,
        }
        dirtyRef.current = true
        if (t < 1) requestAnimationFrame(step)
        else clearCameraFocusAnchorIds()
      }
      requestAnimationFrame(step)
    })

    return () => cancelAnimationFrame(raf)
  }, [cameraFocusAnchorIds, filteredNodes, resolvedSize.width, resolvedSize.height, clearCameraFocusAnchorIds])

  // ── minimap callbacks ─────────────────────────────────────────────────────────
  const getTransform = useCallback(() => transformRef.current, [])
  const setTransform = useCallback((t: { x: number; y: number; k: number }) => {
    transformRef.current = t
    dirtyRef.current = true
  }, [])

  // ── zoom controls ─────────────────────────────────────────────────────────────
  const zoomBy = useCallback(
    (factor: number) => {
      const { x: tx, y: ty, k } = transformRef.current
      const nk = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, k * factor))
      const cx = resolvedSize.width / 2, cy = resolvedSize.height / 2
      transformRef.current = { k: nk, x: cx - (cx - tx) * (nk / k), y: cy - (cy - ty) * (nk / k) }
      dirtyRef.current = true
    },
    [resolvedSize.width, resolvedSize.height],
  )

  const resetZoom = useCallback(() => {
    const sim = simRef.current
    if (!sim?.nodes().length) return
    const ns = sim.nodes()
    const xs = ns.map((n) => n.x ?? 0), ys = ns.map((n) => n.y ?? 0)
    const mnX = Math.min(...xs), mxX = Math.max(...xs)
    const mnY = Math.min(...ys), mxY = Math.max(...ys)
    const cw = mxX - mnX || 1, ch = mxY - mnY || 1
    const margin = 40
    const k = Math.max(0.1, 0.92 * Math.min((resolvedSize.width - 2 * margin) / cw, (resolvedSize.height - 2 * margin) / ch))
    transformRef.current = {
      k,
      x: resolvedSize.width / 2 - k * (mnX + cw / 2),
      y: resolvedSize.height / 2 - k * (mnY + ch / 2),
    }
    dirtyRef.current = true
  }, [resolvedSize.width, resolvedSize.height])

  return (
    <div className="w-full h-full bg-zinc-950 relative">
      <canvas ref={canvasRef} className="block" style={{ cursor: 'grab' }} />
      <LassoActionBar filteredNodes={filteredNodes} onNodeDoubleClick={onNodeDoubleClick} />
      <GraphMinimap
        nodes={filteredNodes}
        viewportWidth={resolvedSize.width}
        viewportHeight={resolvedSize.height}
        getTransform={getTransform}
        setTransform={setTransform}
      />
      <div className="absolute right-3 bottom-3 z-20 flex items-center gap-1 rounded border border-zinc-700 bg-zinc-900/85 p-1">
        <button
          type="button"
          onClick={() => zoomBy(1.2)}
          className="h-8 w-8 rounded bg-zinc-800 text-zinc-200 hover:bg-zinc-700"
          aria-label="Zoom in"
          title="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          onClick={() => zoomBy(0.8)}
          className="h-8 w-8 rounded bg-zinc-800 text-zinc-200 hover:bg-zinc-700"
          aria-label="Zoom out"
          title="Zoom out"
        >
          -
        </button>
        <button
          type="button"
          onClick={resetZoom}
          className="h-8 rounded bg-zinc-800 px-2 text-xs font-medium text-zinc-200 hover:bg-zinc-700"
          aria-label="Reset zoom"
          title="Reset zoom"
        >
          Reset
        </button>
      </div>
    </div>
  )
}
