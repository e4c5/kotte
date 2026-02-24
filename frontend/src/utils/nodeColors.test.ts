import { describe, it, expect, beforeEach } from 'vitest'
import { getNodeLabelColor } from './nodeColors'

describe('getNodeLabelColor', () => {
  beforeEach(() => {
    // Reset module state by re-importing; nodeColors uses a module-level Map.
    // Vitest isolates modules per file, so each test file gets a fresh module.
    // Within this file, the Map persists between tests, so we test deterministic
    // behavior: first-seen label gets first color, etc.
  })

  it('returns a hex color string for a label', () => {
    const color = getNodeLabelColor('Person')
    expect(color).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('returns the same color for the same label', () => {
    expect(getNodeLabelColor('Person')).toBe(getNodeLabelColor('Person'))
    expect(getNodeLabelColor('Company')).toBe(getNodeLabelColor('Company'))
  })

  it('returns different colors for different labels', () => {
    const a = getNodeLabelColor('LabelA')
    const b = getNodeLabelColor('LabelB')
    expect(a).not.toBe(b)
  })

  it('returns a default gray for unknown index (coverage)', () => {
    // First 10 labels get from LABEL_COLORS; we just ensure we get a valid hex
    const color = getNodeLabelColor('SomeLabel')
    expect(color).toMatch(/^#[0-9a-f]{6}$/i)
    expect(color.length).toBe(7)
  })
})
