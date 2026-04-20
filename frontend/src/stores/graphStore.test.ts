/**
 * Unit tests for `graphStore`.
 *
 * Currently scoped to the camera-focus surface introduced for ROADMAP A11
 * phase 2 (`cameraFocusAnchorIds`, `setCameraFocusAnchorIds`,
 * `clearCameraFocusAnchorIds`). The store predates this file, so existing
 * actions (filters, styles, pin/hide) intentionally stay untested here —
 * they have indirect coverage through component tests.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useGraphStore } from './graphStore'

describe('graphStore — camera focus (A11.2)', () => {
  beforeEach(() => {
    useGraphStore.getState().clearCameraFocusAnchorIds()
  })

  afterEach(() => {
    useGraphStore.getState().clearCameraFocusAnchorIds()
  })

  it('starts with an empty anchor list', () => {
    expect(useGraphStore.getState().cameraFocusAnchorIds).toEqual([])
  })

  it('setCameraFocusAnchorIds replaces the anchor list', () => {
    useGraphStore.getState().setCameraFocusAnchorIds(['a', 'b', 'c'])
    expect(useGraphStore.getState().cameraFocusAnchorIds).toEqual(['a', 'b', 'c'])

    useGraphStore.getState().setCameraFocusAnchorIds(['x'])
    expect(useGraphStore.getState().cameraFocusAnchorIds).toEqual(['x'])
  })

  it('setCameraFocusAnchorIds dedups its input', () => {
    useGraphStore.getState().setCameraFocusAnchorIds(['a', 'a', 'b', 'a'])
    expect(useGraphStore.getState().cameraFocusAnchorIds).toEqual(['a', 'b'])
  })

  it('clearCameraFocusAnchorIds resets to []', () => {
    useGraphStore.getState().setCameraFocusAnchorIds(['a'])
    useGraphStore.getState().clearCameraFocusAnchorIds()
    expect(useGraphStore.getState().cameraFocusAnchorIds).toEqual([])
  })

  it('clearCameraFocusAnchorIds is a no-op when already empty (preserves identity)', () => {
    // The reducer skips the set() entirely when the list is already empty so
    // GraphView's effect doesn't re-fire on every component re-render that
    // happens to call clear() defensively.
    const before = useGraphStore.getState().cameraFocusAnchorIds
    useGraphStore.getState().clearCameraFocusAnchorIds()
    const after = useGraphStore.getState().cameraFocusAnchorIds
    expect(after).toBe(before)
  })

  it('setCameraFocusAnchorIds([]) replaces with a fresh empty array', () => {
    // Explicit empty input is treated as a real "clear" — distinct from the
    // identity-preserving optimisation in clearCameraFocusAnchorIds because
    // the caller's intent is to overwrite, not just defensively reset.
    useGraphStore.getState().setCameraFocusAnchorIds(['a'])
    useGraphStore.getState().setCameraFocusAnchorIds([])
    expect(useGraphStore.getState().cameraFocusAnchorIds).toEqual([])
  })
})
