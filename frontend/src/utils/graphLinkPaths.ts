/** Minimal node/edge shapes for geometry (keeps this module free of GraphView import cycles). */
export interface LinkGeomNode {
  id: string
  x?: number
  y?: number
}

export interface LinkGeomEdge {
  id: string
  source: string | LinkGeomNode
  target: string | LinkGeomNode
}

export interface ParallelEdgeMeta {
  index: number
  count: number
}

/** Stable groups by directed (source, target); used for parallel edge offsets. */
export function parallelEdgeMeta(edges: LinkGeomEdge[]): Map<string, ParallelEdgeMeta> {
  const groups = new Map<string, LinkGeomEdge[]>()
  for (const e of edges) {
    const s = typeof e.source === 'string' ? e.source : e.source.id
    const t = typeof e.target === 'string' ? e.target : e.target.id
    const key = `${s}\0${t}`
    let list = groups.get(key)
    if (!list) {
      list = []
      groups.set(key, list)
    }
    list.push(e)
  }
  const meta = new Map<string, ParallelEdgeMeta>()
  for (const list of groups.values()) {
    list.sort((a, b) => a.id.localeCompare(b.id))
    const count = list.length
    list.forEach((e, index) => {
      meta.set(e.id, { index, count })
    })
  }
  return meta
}

function nodeRadius<N extends LinkGeomNode>(node: N | undefined, getR: (n: N) => number): number {
  return node ? getR(node) : 12
}

export interface LinkPathResult {
  d: string
  /** Midpoint on the curve (for labels). */
  lx: number
  ly: number
}

const LOOP_BASE_LIFT = 26
const LOOP_STEP = 16
const CURVE_OFFSET_STEP = 12

/**
 * Builds SVG path `d`, shortened to node rims, with quadratic curve and parallel offset.
 * Self-loops use a symmetric arc above the node; `parallelMeta` index spreads multiple loops.
 */
export function linkPath<N extends LinkGeomNode>(
  edge: { id: string; source: string | N; target: string | N },
  getNode: (endpoint: string | N) => N | undefined,
  getNodeR: (n: N) => number,
  parallel: ParallelEdgeMeta | undefined
): LinkPathResult {
  const sNode = getNode(edge.source)
  const tNode = getNode(edge.target)
  const sx = sNode?.x ?? 0
  const sy = sNode?.y ?? 0
  const tx = tNode?.x ?? 0
  const ty = tNode?.y ?? 0

  const sid = typeof edge.source === 'string' ? edge.source : edge.source.id
  const tid = typeof edge.target === 'string' ? edge.target : edge.target.id

  if (sid === tid && sNode) {
    const r = nodeRadius(sNode, getNodeR)
    const idx = parallel?.index ?? 0
    const lift = LOOP_BASE_LIFT + idx * LOOP_STEP
    const spread = Math.min(18, r * 0.9)
    const x0 = sx + spread
    const y0 = sy - r * 0.2
    const x1 = sx - spread
    const y1 = sy - r * 0.2
    const qx = sx
    const qy = sy - r - lift
    const d = `M ${x0} ${y0} Q ${qx} ${qy} ${x1} ${y1}`
    const lx = 0.25 * x0 + 0.5 * qx + 0.25 * x1
    const ly = 0.25 * y0 + 0.5 * qy + 0.25 * y1
    return { d, lx, ly }
  }

  const rS = nodeRadius(sNode, getNodeR)
  const rT = nodeRadius(tNode, getNodeR)
  let dx = tx - sx
  let dy = ty - sy
  const len = Math.hypot(dx, dy)
  if (len < 1e-6) {
    const d = `M ${sx} ${sy} L ${sx + 0.01} ${sy + 0.01}`
    return { d, lx: sx, ly: sy }
  }
  dx /= len
  dy /= len

  const x0 = sx + dx * rS
  const y0 = sy + dy * rS
  const x1 = tx - dx * rT
  const y1 = ty - dy * rT

  const mx = (x0 + x1) / 2
  const my = (y0 + y1) / 2
  const px = -dy
  const py = dx
  const count = parallel?.count ?? 1
  const index = parallel?.index ?? 0
  const offset = (index - (count - 1) / 2) * CURVE_OFFSET_STEP
  const cx = mx + px * offset
  const cy = my + py * offset

  const d = `M ${x0} ${y0} Q ${cx} ${cy} ${x1} ${y1}`
  const lx = 0.25 * x0 + 0.5 * cx + 0.25 * x1
  const ly = 0.25 * y0 + 0.5 * cy + 0.25 * y1
  return { d, lx, ly }
}

/** Sanitize hex color for use in an SVG id fragment. */
export function markerIdForColor(hex: string): string {
  const safe = hex.replace(/[^a-zA-Z0-9]/g, '') || 'default'
  return `kotte-arrow-${safe}`
}
