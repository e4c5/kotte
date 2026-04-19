import { describe, it, expect } from 'vitest'
import type { GraphNode } from '../components/GraphView'
import { getDefaultNodeColor, getNodeStyle } from './graphStyles'
import { getNodeLabelColor } from './nodeColors'

/**
 * Regression tests for ROADMAP A6 — colour-palette unification.
 *
 * Before A6, `graphStyles` owned a private `d3.scaleOrdinal` and `nodeColors`
 * owned a separate insertion-order `Map`, so the same label could land on
 * different palette indices in the two modules. The metadata-sidebar pill and
 * the graph-canvas circle for the same label could end up different colours.
 *
 * These tests pin down the contract:
 *   1. `getDefaultNodeColor` and `getNodeLabelColor` agree for any label.
 *   2. `getNodeStyle(node, {})` (i.e. no user override) uses that same colour.
 *   3. Order of first call doesn't matter — graph-side first or sidebar-side
 *      first, both surfaces converge on the same hex.
 *   4. User-supplied `nodeStyles` still wins over the default.
 */

const makeNode = (label: string): GraphNode => ({
  id: `${label}-id`,
  label,
  properties: {},
})

describe('graphStyles — unified colour palette (ROADMAP A6)', () => {
  it('getDefaultNodeColor returns the same hex as getNodeLabelColor for a label', () => {
    const label = 'A6_Label_Default_Match'
    expect(getDefaultNodeColor(label)).toBe(getNodeLabelColor(label))
  })

  it('getNodeStyle (no override) reports the same colour as the sidebar helper', () => {
    const label = 'A6_Label_NodeStyle_Match'
    const style = getNodeStyle(makeNode(label), {})
    expect(style.color).toBe(getNodeLabelColor(label))
  })

  it('graph-side first then sidebar-side: both observe the same hex', () => {
    const label = 'A6_Label_Graph_First'
    const fromGraph = getNodeStyle(makeNode(label), {}).color
    const fromSidebar = getNodeLabelColor(label)
    expect(fromSidebar).toBe(fromGraph)
  })

  it('sidebar-side first then graph-side: both observe the same hex', () => {
    const label = 'A6_Label_Sidebar_First'
    const fromSidebar = getNodeLabelColor(label)
    const fromGraph = getNodeStyle(makeNode(label), {}).color
    expect(fromGraph).toBe(fromSidebar)
  })

  it('returns a valid hex colour', () => {
    expect(getDefaultNodeColor('A6_Label_Hex_Shape')).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('different labels get different colours (within the 10-slot palette)', () => {
    const a = getDefaultNodeColor('A6_Label_Distinct_A')
    const b = getDefaultNodeColor('A6_Label_Distinct_B')
    expect(a).not.toBe(b)
  })

  it('user-supplied nodeStyles still override the unified default', () => {
    const label = 'A6_Label_Override'
    const override = { color: '#abcdef', size: 20, captionField: 'name' }
    const style = getNodeStyle(makeNode(label), { [label]: override })
    expect(style).toEqual(override)
    expect(style.color).not.toBe(getNodeLabelColor(label))
  })
})
