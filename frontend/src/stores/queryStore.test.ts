/**
 * Unit tests for `queryStore` — scoped to the isolate / restore surface
 * introduced for ROADMAP A11 phase 3 (`isolateNeighborhood`,
 * `restoreGraphElements`, `previousGraphElements`).
 *
 * The wider store (tab CRUD, executeQuery, history) predates this file and
 * is intentionally not retro-tested here — these tests pin the new contract
 * the WorkspacePage / ResultTab wiring depends on.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useQueryStore } from './queryStore'
import type { QueryExecuteResponse } from '../services/query'
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
  label = 'KNOWS',
): GraphEdge => ({
  id,
  label,
  source,
  target,
  properties: {},
  type: 'edge',
})

const makeResult = (
  nodes: GraphNode[],
  edges: GraphEdge[],
): QueryExecuteResponse => ({
  columns: ['n'],
  rows: [],
  row_count: 0,
  request_id: 'req-1',
  stats: { nodes_extracted: nodes.length, edges_extracted: edges.length },
  graph_elements: {
    nodes,
    edges: edges.map((e) => ({ ...e })),
  } as QueryExecuteResponse['graph_elements'],
})

function resetStore() {
  // The store has no public reset, so we reach in. This only affects the
  // in-memory copy used by Vitest workers.
  useQueryStore.setState({
    tabs: [],
    activeTabId: null,
    history: [],
    historyIndex: -1,
  })
}

function seedTab(result: QueryExecuteResponse) {
  resetStore()
  const id = useQueryStore.getState().createTab('T1')
  useQueryStore.getState().updateTab(id, { result })
  return id
}

describe('queryStore — isolateNeighborhood / restoreGraphElements (A11.3)', () => {
  beforeEach(resetStore)
  afterEach(resetStore)

  it('isolates the clicked node + its incident edges + their endpoints', () => {
    // Canvas: a -[e1]- b -[e2]- c, plus an unrelated d -[e3]- e
    const result = makeResult(
      [node('a'), node('b'), node('c'), node('d'), node('e')],
      [edge('e1', 'a', 'b'), edge('e2', 'b', 'c'), edge('e3', 'd', 'e')],
    )
    const tabId = seedTab(result)

    useQueryStore.getState().isolateNeighborhood(tabId, 'b')
    const tab = useQueryStore.getState().tabs.find((t) => t.id === tabId)!

    const keptIds = (tab.result?.graph_elements?.nodes ?? []).map((n) => n.id).sort()
    const keptEdgeIds = (tab.result?.graph_elements?.edges ?? []).map((e) => e.id).sort()

    expect(keptIds).toEqual(['a', 'b', 'c'])
    expect(keptEdgeIds).toEqual(['e1', 'e2'])
  })

  it('snapshots the prior graph_elements onto previousGraphElements', () => {
    const result = makeResult(
      [node('a'), node('b'), node('c')],
      [edge('e1', 'a', 'b'), edge('e2', 'b', 'c')],
    )
    const tabId = seedTab(result)

    useQueryStore.getState().isolateNeighborhood(tabId, 'a')
    const tab = useQueryStore.getState().tabs.find((t) => t.id === tabId)!

    expect(tab.previousGraphElements).toBeTruthy()
    expect((tab.previousGraphElements?.nodes ?? []).map((n) => n.id).sort()).toEqual([
      'a',
      'b',
      'c',
    ])
    expect((tab.previousGraphElements?.edges ?? []).map((e) => e.id).sort()).toEqual([
      'e1',
      'e2',
    ])
  })

  it('restoreGraphElements puts the original canvas back exactly and clears the snapshot', () => {
    const originalNodes = [node('a'), node('b'), node('c'), node('d')]
    const originalEdges = [edge('e1', 'a', 'b'), edge('e2', 'b', 'c'), edge('e3', 'c', 'd')]
    const result = makeResult(originalNodes, originalEdges)
    const tabId = seedTab(result)

    useQueryStore.getState().isolateNeighborhood(tabId, 'b')
    useQueryStore.getState().restoreGraphElements(tabId)

    const tab = useQueryStore.getState().tabs.find((t) => t.id === tabId)!
    const restoredIds = (tab.result?.graph_elements?.nodes ?? []).map((n) => n.id).sort()
    const restoredEdgeIds = (tab.result?.graph_elements?.edges ?? []).map((e) => e.id).sort()

    expect(restoredIds).toEqual(['a', 'b', 'c', 'd'])
    expect(restoredEdgeIds).toEqual(['e1', 'e2', 'e3'])
    expect(tab.previousGraphElements).toBeNull()
  })

  it('isolateNeighborhood is a no-op when the tab is already isolated', () => {
    // Without this guard, a second isolate would overwrite the snapshot with
    // the already-narrowed canvas and the breadcrumb would lose the original.
    const result = makeResult(
      [node('a'), node('b'), node('c')],
      [edge('e1', 'a', 'b'), edge('e2', 'b', 'c')],
    )
    const tabId = seedTab(result)

    useQueryStore.getState().isolateNeighborhood(tabId, 'b')
    const snapshot = useQueryStore.getState().tabs.find((t) => t.id === tabId)
      ?.previousGraphElements
    useQueryStore.getState().isolateNeighborhood(tabId, 'a')
    const after = useQueryStore.getState().tabs.find((t) => t.id === tabId)
      ?.previousGraphElements

    expect(after).toBe(snapshot)
  })

  it('restoreGraphElements is a no-op when no snapshot exists', () => {
    const result = makeResult([node('a'), node('b')], [edge('e1', 'a', 'b')])
    const tabId = seedTab(result)

    useQueryStore.getState().restoreGraphElements(tabId)
    const tab = useQueryStore.getState().tabs.find((t) => t.id === tabId)!

    expect(tab.previousGraphElements ?? null).toBeNull()
    expect((tab.result?.graph_elements?.nodes ?? []).map((n) => n.id)).toEqual(['a', 'b'])
  })

  it('isolating a node with no incident edges keeps just that node', () => {
    // Edge case: user right-clicks a freshly-pasted node that hasn't been
    // expanded yet. The breadcrumb is still the path back.
    const result = makeResult(
      [node('a'), node('b'), node('lonely')],
      [edge('e1', 'a', 'b')],
    )
    const tabId = seedTab(result)

    useQueryStore.getState().isolateNeighborhood(tabId, 'lonely')
    const tab = useQueryStore.getState().tabs.find((t) => t.id === tabId)!

    expect((tab.result?.graph_elements?.nodes ?? []).map((n) => n.id)).toEqual(['lonely'])
    expect((tab.result?.graph_elements?.edges ?? [])).toEqual([])
  })

  it('does nothing if the tab has no graph_elements', () => {
    const result: QueryExecuteResponse = {
      columns: ['n'],
      rows: [],
      row_count: 0,
      request_id: 'req-1',
    }
    const tabId = seedTab(result)

    useQueryStore.getState().isolateNeighborhood(tabId, 'a')
    const tab = useQueryStore.getState().tabs.find((t) => t.id === tabId)!

    expect(tab.previousGraphElements ?? null).toBeNull()
    expect(tab.result?.graph_elements ?? null).toBeNull()
  })
})
