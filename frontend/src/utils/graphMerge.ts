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
 * Merge `incoming` into `existing` without mutating either.
 *
 * TODO(A11): implement. Tests in graphMerge.test.ts define the contract.
 */
export function mergeGraphElements(
  _existing: GraphElements,
  _incoming: GraphElements
): MergeResult {
  throw new Error('mergeGraphElements: not yet implemented (see docs/ROADMAP.md A11)')
}
