/**
 * Minimap overlay for both SVG and Canvas graph renderers (C2.5).
 * Renders node positions at low frequency (~10 fps) and a viewport rect.
 * Click or drag to pan the main view.
 */

import { useEffect, useRef } from 'react'
import { getNodeLabelColor } from '../utils/nodeColors'
import type { GraphNode } from './GraphView'

export const MINIMAP_W = 160
export const MINIMAP_H = 120
const NODE_R = 2
const PAD = 10

interface WorldMapping {
  scaleM: number
  offsetX: number
  offsetY: number
  worldMinX: number
  worldMinY: number
}

export interface GraphMinimapProps {
  readonly nodes: GraphNode[]
  readonly viewportWidth: number
  readonly viewportHeight: number
  /** Read the current viewport transform — called every draw frame. */
  readonly getTransform: () => { x: number; y: number; k: number }
  /** Apply a new viewport transform from a minimap interaction. */
  readonly setTransform: (t: { x: number; y: number; k: number }) => void
}

export default function GraphMinimap({
  nodes,
  viewportWidth,
  viewportHeight,
  getTransform,
  setTransform,
}: GraphMinimapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawRef = useRef<(() => void) | null>(null)
  const mappingRef = useRef<WorldMapping | null>(null)

  // ── DPR setup ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = globalThis.devicePixelRatio || 1
    canvas.width = MINIMAP_W * dpr
    canvas.height = MINIMAP_H * dpr
    canvas.style.width = `${MINIMAP_W}px`
    canvas.style.height = `${MINIMAP_H}px`
  }, [])

  // ── draw closure — updated whenever nodes / viewport dims change ───────────
  useEffect(() => {
    drawRef.current = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const dpr = globalThis.devicePixelRatio || 1

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, MINIMAP_W, MINIMAP_H)
      ctx.fillStyle = 'rgba(9,9,11,0.88)'
      ctx.fillRect(0, 0, MINIMAP_W, MINIMAP_H)

      // World bounding box from live node positions (mutated in-place by d3-force).
      const valid = nodes.filter((n) => n.x != null && n.y != null)
      if (!valid.length) {
        mappingRef.current = null
        // Border only
        ctx.strokeStyle = 'rgba(113,113,122,0.4)'
        ctx.lineWidth = 1
        ctx.strokeRect(0.5, 0.5, MINIMAP_W - 1, MINIMAP_H - 1)
        return
      }

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
      for (const n of valid) {
        if (n.x! < minX) minX = n.x!
        if (n.x! > maxX) maxX = n.x!
        if (n.y! < minY) minY = n.y!
        if (n.y! > maxY) maxY = n.y!
      }

      const worldW = maxX - minX || 1
      const worldH = maxY - minY || 1
      const scaleM = Math.min(
        (MINIMAP_W - 2 * PAD) / worldW,
        (MINIMAP_H - 2 * PAD) / worldH,
      )
      const offsetX = PAD + ((MINIMAP_W - 2 * PAD) - worldW * scaleM) / 2
      const offsetY = PAD + ((MINIMAP_H - 2 * PAD) - worldH * scaleM) / 2
      mappingRef.current = { scaleM, offsetX, offsetY, worldMinX: minX, worldMinY: minY }

      const wx = (x: number) => (x - minX) * scaleM + offsetX
      const wy = (y: number) => (y - minY) * scaleM + offsetY

      // Nodes
      for (const n of valid) {
        ctx.beginPath()
        ctx.arc(wx(n.x!), wy(n.y!), NODE_R, 0, Math.PI * 2)
        ctx.fillStyle = getNodeLabelColor(n.label)
        ctx.fill()
      }

      // Viewport rect
      const { x: tx, y: ty, k } = getTransform()
      const vLeft = (0 - tx) / k
      const vTop = (0 - ty) / k
      const vRight = (viewportWidth - tx) / k
      const vBottom = (viewportHeight - ty) / k

      const rx = wx(vLeft)
      const ry = wy(vTop)
      const rw = (vRight - vLeft) * scaleM
      const rh = (vBottom - vTop) * scaleM

      ctx.fillStyle = 'rgba(255,255,255,0.06)'
      ctx.fillRect(rx, ry, rw, rh)
      ctx.strokeStyle = 'rgba(255,255,255,0.55)'
      ctx.lineWidth = 1
      ctx.strokeRect(rx, ry, rw, rh)

      // Border
      ctx.strokeStyle = 'rgba(113,113,122,0.4)'
      ctx.lineWidth = 1
      ctx.strokeRect(0.5, 0.5, MINIMAP_W - 1, MINIMAP_H - 1)
    }
  }, [nodes, viewportWidth, viewportHeight, getTransform])

  // ── RAF loop at ~10 fps ────────────────────────────────────────────────────
  useEffect(() => {
    let rafId: number
    let lastTs = 0
    function loop(ts: number) {
      if (ts - lastTs > 100 && drawRef.current) {
        drawRef.current()
        lastTs = ts
      }
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [])

  // ── pointer interaction ────────────────────────────────────────────────────
  const dragRef = useRef<{
    startMx: number
    startMy: number
    startTx: number
    startTy: number
  } | null>(null)

  function toWorld(mx: number, my: number): [number, number] | null {
    const m = mappingRef.current
    if (!m) return null
    return [(mx - m.offsetX) / m.scaleM + m.worldMinX, (my - m.offsetY) / m.scaleM + m.worldMinY]
  }

  function onPointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    e.currentTarget.setPointerCapture(e.pointerId)
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const t = getTransform()
    dragRef.current = { startMx: mx, startMy: my, startTx: t.x, startTy: t.y }
  }

  function onPointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    const d = dragRef.current
    const m = mappingRef.current
    if (!d || !m) return
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const dWorldX = (mx - d.startMx) / m.scaleM
    const dWorldY = (my - d.startMy) / m.scaleM
    const { k } = getTransform()
    setTransform({ k, x: d.startTx - dWorldX * k, y: d.startTy - dWorldY * k })
  }

  function onPointerUp(e: React.PointerEvent<HTMLCanvasElement>) {
    const d = dragRef.current
    if (!d) return
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    // Click (no significant drag) → center viewport on clicked world point
    if (Math.hypot(mx - d.startMx, my - d.startMy) < 5) {
      const world = toWorld(mx, my)
      if (world) {
        const { k } = getTransform()
        setTransform({
          k,
          x: viewportWidth / 2 - k * world[0],
          y: viewportHeight / 2 - k * world[1],
        })
      }
    }
    dragRef.current = null
  }

  function onPointerCancel(e: React.PointerEvent<HTMLCanvasElement>) {
    dragRef.current = null
    e.currentTarget.releasePointerCapture(e.pointerId)
  }

  return (
    <canvas
      ref={canvasRef}
      className="absolute left-3 bottom-3 z-20 rounded cursor-crosshair select-none"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
      title="Minimap — click or drag to navigate"
      aria-label="Graph minimap"
    />
  )
}
