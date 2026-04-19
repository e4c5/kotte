/**
 * Pure helpers for additively merging graph elements (nodes + edges)
 * fetched from incremental expansions into an existing visualization.
 *
 * Replaces the destructive replace-graph behaviour previously used by
 * `handleFocusNode` in WorkspacePage and consolidates the ad-hoc
 * merge logic currently embedded in `queryStore.mergeGraphElements`.
 *
 * Design goals:
 *   1. Purity — never mutate the inputs; always return new arrays.
 *   2. Stable dedup — nodes by `id`; edges by `(source, target, label)`
 *      so that AGE-generated edge ids (which can collide across
 *      expansions of the same neighbourhood) don't produce duplicates.
 *   3. Provenance — return the ids that were *newly* added so the
 *      caller can animate the camera or briefly pin them.
 *
 * See docs/ROADMAP.md §A11 for the wider plan this scaffolds.
 */

import type { GraphEdge, GraphNode } from '../services/graph'

export interface GraphElements {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface MergeResult extends GraphElements {
  added: {
    nodeIds: string[]
    edgeIds: string[]
  }
}

/**
 * Extract the id from an edge endpoint, which may be either a raw id
 * string or a `GraphNode` object (D3's force layout mutates string
 * endpoints into object references after the first simulation tick).
 */
const endpointId = (endpoint: string | GraphNode): string =>
  typeof endpoint === 'string' ? endpoint : endpoint.id

/**
 * Compose a stable dedup key for an edge from `(source-id, target-id, label)`.
 * Edge ids are NOT used: AGE generates fresh edge ids on each expansion, so
 * id-based dedup silently produces duplicate links each time the same
 * neighbourhood is re-fetched.
 */
const edgeKey = (e: GraphEdge): string =>
  `${endpointId(e.source)}\u0000${endpointId(e.target)}\u0000${e.label}`

/**
 * Merge `incoming` into `existing` without mutating either.
 *
 * - Nodes are deduped by `id`; the existing copy is preferred so that
 *   in-progress force-layout coordinates and user-visible properties
 *   are not clobbered by a freshly-fetched (and possibly stale) version.
 * - Edges are deduped by `(source, target, label)` — see {@link edgeKey}.
 * - The `added` payload reports the ids that were newly inserted, in
 *   insertion order, so callers can animate camera focus or briefly pin
 *   newcomers without re-deriving the diff.
 */
export function mergeGraphElements(
  existing: GraphElements,
  incoming: GraphElements
): MergeResult {
  const mergedNodes: GraphNode[] = [...existing.nodes]
  const seenNodeIds = new Set(existing.nodes.map((n) => n.id))
  const addedNodeIds: string[] = []

  for (const node of incoming.nodes) {
    if (seenNodeIds.has(node.id)) continue
    seenNodeIds.add(node.id)
    mergedNodes.push(node)
    addedNodeIds.push(node.id)
  }

  const mergedEdges: GraphEdge[] = [...existing.edges]
  const seenEdgeKeys = new Set(existing.edges.map(edgeKey))
  const addedEdgeIds: string[] = []

  for (const edge of incoming.edges) {
    const key = edgeKey(edge)
    if (seenEdgeKeys.has(key)) continue
    seenEdgeKeys.add(key)
    mergedEdges.push(edge)
    addedEdgeIds.push(edge.id)
  }

  return {
    nodes: mergedNodes,
    edges: mergedEdges,
    added: { nodeIds: addedNodeIds, edgeIds: addedEdgeIds },
  }
}
