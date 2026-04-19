import { describe, it, expect } from 'vitest'
import { mergeGraphElements, type GraphElements } from './graphMerge'
import type { GraphEdge, GraphNode } from '../services/graph'

const node = (id: string, label = 'Person'): GraphNode => ({
  id,
  label,
  properties: {},
  type: 'node',
})

const edge = (
  id: string,
  source: string,
  target: string,
  label = 'KNOWS'
): GraphEdge => ({
  id,
  label,
  source,
  target,
  properties: {},
  type: 'edge',
})

const empty = (): GraphElements => ({ nodes: [], edges: [] })

describe('mergeGraphElements', () => {
  it('returns the existing elements unchanged when incoming is empty', () => {
    const existing: GraphElements = { nodes: [node('a')], edges: [edge('e1', 'a', 'a')] }
    const result = mergeGraphElements(existing, empty())

    expect(result.nodes).toHaveLength(1)
    expect(result.edges).toHaveLength(1)
    expect(result.added.nodeIds).toEqual([])
    expect(result.added.edgeIds).toEqual([])
  })

  it('does not mutate the inputs (purity)', () => {
    const existingNodes = [node('a')]
    const existingEdges = [edge('e1', 'a', 'a')]
    const existing: GraphElements = { nodes: existingNodes, edges: existingEdges }
    const incoming: GraphElements = { nodes: [node('b')], edges: [edge('e2', 'a', 'b')] }

    mergeGraphElements(existing, incoming)

    expect(existingNodes).toHaveLength(1)
    expect(existingEdges).toHaveLength(1)
    expect(existing.nodes).toBe(existingNodes)
    expect(existing.edges).toBe(existingEdges)
  })

  it('adds nodes that are not already present', () => {
    const existing: GraphElements = { nodes: [node('a')], edges: [] }
    const incoming: GraphElements = { nodes: [node('b'), node('c')], edges: [] }

    const result = mergeGraphElements(existing, incoming)

    expect(result.nodes.map((n) => n.id).sort()).toEqual(['a', 'b', 'c'])
    expect(result.added.nodeIds.sort()).toEqual(['b', 'c'])
  })

  it('dedupes nodes by id and prefers the existing copy', () => {
    const original = node('a', 'Person')
    const duplicate = { ...node('a', 'Person'), properties: { name: 'changed' } }
    const existing: GraphElements = { nodes: [original], edges: [] }
    const incoming: GraphElements = { nodes: [duplicate], edges: [] }

    const result = mergeGraphElements(existing, incoming)

    expect(result.nodes).toHaveLength(1)
    expect(result.nodes[0]).toBe(original)
    expect(result.added.nodeIds).toEqual([])
  })

  it('never removes existing nodes or edges (additive only)', () => {
    const existing: GraphElements = {
      nodes: [node('a'), node('b'), node('c')],
      edges: [edge('e1', 'a', 'b'), edge('e2', 'b', 'c')],
    }
    const incoming: GraphElements = { nodes: [node('d')], edges: [edge('e3', 'c', 'd')] }

    const result = mergeGraphElements(existing, incoming)

    expect(result.nodes.map((n) => n.id).sort()).toEqual(['a', 'b', 'c', 'd'])
    expect(result.edges.map((e) => e.id).sort()).toEqual(['e1', 'e2', 'e3'])
  })

  it('dedupes edges by (source, target, label) even when ids differ', () => {
    const existing: GraphElements = { nodes: [node('a'), node('b')], edges: [edge('e1', 'a', 'b', 'KNOWS')] }
    const incoming: GraphElements = {
      nodes: [],
      edges: [edge('e2-different-id', 'a', 'b', 'KNOWS')],
    }

    const result = mergeGraphElements(existing, incoming)

    expect(result.edges).toHaveLength(1)
    expect(result.edges[0].id).toBe('e1')
    expect(result.added.edgeIds).toEqual([])
  })

  it('treats edges with different labels between the same nodes as distinct', () => {
    const existing: GraphElements = { nodes: [node('a'), node('b')], edges: [edge('e1', 'a', 'b', 'KNOWS')] }
    const incoming: GraphElements = { nodes: [], edges: [edge('e2', 'a', 'b', 'WORKS_WITH')] }

    const result = mergeGraphElements(existing, incoming)

    expect(result.edges).toHaveLength(2)
    expect(result.added.edgeIds).toEqual(['e2'])
  })

  it('treats edges with reversed direction as distinct (directed graph)', () => {
    const existing: GraphElements = { nodes: [node('a'), node('b')], edges: [edge('e1', 'a', 'b', 'KNOWS')] }
    const incoming: GraphElements = { nodes: [], edges: [edge('e2', 'b', 'a', 'KNOWS')] }

    const result = mergeGraphElements(existing, incoming)

    expect(result.edges).toHaveLength(2)
    expect(result.added.edgeIds).toEqual(['e2'])
  })

  it('handles edges whose source/target are GraphNode objects (post-force-layout)', () => {
    const a = node('a')
    const b = node('b')
    const existing: GraphElements = { nodes: [a, b], edges: [{ ...edge('e1', 'a', 'b'), source: a, target: b }] }
    const incoming: GraphElements = { nodes: [], edges: [edge('e2-different-id', 'a', 'b', 'KNOWS')] }

    const result = mergeGraphElements(existing, incoming)

    expect(result.edges).toHaveLength(1)
    expect(result.added.edgeIds).toEqual([])
  })

  it('reports added nodes and edges in insertion order', () => {
    const existing: GraphElements = { nodes: [node('a')], edges: [] }
    const incoming: GraphElements = {
      nodes: [node('b'), node('c'), node('a')],
      edges: [edge('e1', 'a', 'b'), edge('e2', 'b', 'c')],
    }

    const result = mergeGraphElements(existing, incoming)

    expect(result.added.nodeIds).toEqual(['b', 'c'])
    expect(result.added.edgeIds).toEqual(['e1', 'e2'])
  })
})
