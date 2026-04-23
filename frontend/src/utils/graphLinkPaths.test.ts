import { describe, expect, it } from 'vitest'
import { linkPath, parallelEdgeMeta, type LinkGeomEdge } from './graphLinkPaths'

describe('parallelEdgeMeta', () => {
  it('assigns stable indices per directed pair', () => {
    const edges: LinkGeomEdge[] = [
      { id: 'b', source: '1', target: '2' },
      { id: 'a', source: '1', target: '2' },
      { id: 'c', source: '2', target: '1' },
    ]
    const m = parallelEdgeMeta(edges)
    expect(m.get('a')).toEqual({ index: 0, count: 2 })
    expect(m.get('b')).toEqual({ index: 1, count: 2 })
    expect(m.get('c')).toEqual({ index: 0, count: 1 })
  })
})

describe('linkPath', () => {
  const nodes: Record<string, { id: string; x: number; y: number }> = {
    1: { id: '1', x: 0, y: 0 },
    2: { id: '2', x: 100, y: 0 },
  }
  const getNode = (e: string | { id: string; x?: number; y?: number }) =>
    typeof e === 'string' ? nodes[e] : e
  const getR = () => 10

  it('returns a quadratic path between two nodes shortened by radii', () => {
    const { d, lx, ly } = linkPath(
      { id: 'e', source: '1', target: '2' },
      getNode,
      getR,
      { index: 0, count: 1 }
    )
    expect(d).toMatch(/^M [\d.-]+ [\d.-]+ Q [\d.-]+ [\d.-]+ [\d.-]+ [\d.-]+$/)
    expect(lx).toBeGreaterThan(0)
    expect(lx).toBeLessThan(100)
    expect(Number.isFinite(ly)).toBe(true)
  })

  it('offsets parallel edges via control point', () => {
    const base = linkPath(
      { id: 'e0', source: '1', target: '2' },
      getNode,
      getR,
      { index: 0, count: 2 }
    )
    const off = linkPath(
      { id: 'e1', source: '1', target: '2' },
      getNode,
      getR,
      { index: 1, count: 2 }
    )
    expect(base.d).not.toBe(off.d)
  })

  it('draws a self-loop above the node', () => {
    const self = { id: '1', x: 50, y: 50 }
    const getSelf = (e: string | { id: string; x?: number; y?: number }) =>
      typeof e === 'string' ? self : e
    const { d } = linkPath(
      { id: 'loop', source: '1', target: '1' },
      getSelf,
      () => 10,
      { index: 0, count: 1 }
    )
    expect(d).toContain('Q')
    expect(d).toMatch(/^M /)
  })
})
