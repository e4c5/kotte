/**
 * Tests for useTheme — verifies the hook keeps `documentElement.classList`
 * in sync with the persisted theme, and that 'auto' subscribes to + cleans up
 * the prefers-color-scheme media query.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

import { useTheme, isDarkMode } from './useTheme'
import { useSettingsStore } from '../stores/settingsStore'

interface FakeMediaQueryList {
  matches: boolean
  media: string
  addEventListener: ReturnType<typeof vi.fn>
  removeEventListener: ReturnType<typeof vi.fn>
  addListener: ReturnType<typeof vi.fn>
  removeListener: ReturnType<typeof vi.fn>
  dispatchEvent: ReturnType<typeof vi.fn>
  onchange: null
}

function createFakeMedia(matches: boolean): FakeMediaQueryList {
  return {
    matches,
    media: '(prefers-color-scheme: dark)',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onchange: null,
  }
}

describe('useTheme', () => {
  let originalMatchMedia: typeof window.matchMedia | undefined
  let fakeMedia: FakeMediaQueryList

  beforeEach(() => {
    originalMatchMedia = window.matchMedia
    fakeMedia = createFakeMedia(false)
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockReturnValue(fakeMedia),
    })
    document.documentElement.classList.remove('dark')
    useSettingsStore.setState({ theme: 'light' })
  })

  afterEach(() => {
    if (originalMatchMedia) {
      Object.defineProperty(window, 'matchMedia', {
        configurable: true,
        writable: true,
        value: originalMatchMedia,
      })
    }
    document.documentElement.classList.remove('dark')
    useSettingsStore.setState({ theme: 'light' })
  })

  it('adds the dark class when theme is dark', () => {
    useSettingsStore.setState({ theme: 'dark' })
    renderHook(() => useTheme())
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('removes the dark class when theme is light', () => {
    document.documentElement.classList.add('dark')
    useSettingsStore.setState({ theme: 'light' })
    renderHook(() => useTheme())
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('flips the class when theme changes from light to dark', () => {
    const { rerender } = renderHook(() => useTheme())
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    act(() => {
      useSettingsStore.setState({ theme: 'dark' })
    })
    rerender()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('does not subscribe to matchMedia for explicit themes', () => {
    useSettingsStore.setState({ theme: 'dark' })
    renderHook(() => useTheme())
    expect(fakeMedia.addEventListener).not.toHaveBeenCalled()
  })

  it('subscribes to matchMedia in auto mode and reflects the current value', () => {
    fakeMedia.matches = true
    useSettingsStore.setState({ theme: 'auto' })

    renderHook(() => useTheme())

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(fakeMedia.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })

  it('responds to matchMedia change events while in auto mode', () => {
    useSettingsStore.setState({ theme: 'auto' })
    renderHook(() => useTheme())

    const handler = fakeMedia.addEventListener.mock.calls[0][1] as (
      event: MediaQueryListEvent,
    ) => void

    act(() => {
      handler({ matches: true } as MediaQueryListEvent)
    })
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    act(() => {
      handler({ matches: false } as MediaQueryListEvent)
    })
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('removes the matchMedia listener on unmount', () => {
    useSettingsStore.setState({ theme: 'auto' })
    const { unmount } = renderHook(() => useTheme())

    expect(fakeMedia.addEventListener).toHaveBeenCalledTimes(1)
    unmount()
    expect(fakeMedia.removeEventListener).toHaveBeenCalledTimes(1)
  })

  it('falls back to legacy addListener/removeListener when addEventListener is missing', () => {
    const legacyMedia = createFakeMedia(false)
    // Simulate Safari < 14 where addEventListener isn't available on MediaQueryList.
    const mutable = legacyMedia as unknown as Record<string, unknown>
    delete mutable.addEventListener
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockReturnValue(legacyMedia),
    })

    useSettingsStore.setState({ theme: 'auto' })
    const { unmount } = renderHook(() => useTheme())
    expect(legacyMedia.addListener).toHaveBeenCalledTimes(1)

    unmount()
    expect(legacyMedia.removeListener).toHaveBeenCalledTimes(1)
  })
})

describe('isDarkMode', () => {
  let originalMatchMedia: typeof window.matchMedia | undefined

  beforeEach(() => {
    originalMatchMedia = window.matchMedia
  })

  afterEach(() => {
    if (originalMatchMedia) {
      Object.defineProperty(window, 'matchMedia', {
        configurable: true,
        writable: true,
        value: originalMatchMedia,
      })
    }
  })

  it('returns true for explicit dark', () => {
    expect(isDarkMode('dark')).toBe(true)
  })

  it('returns false for explicit light', () => {
    expect(isDarkMode('light')).toBe(false)
  })

  it('mirrors matchMedia in auto mode', () => {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockReturnValue(createFakeMedia(true)),
    })
    expect(isDarkMode('auto')).toBe(true)

    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockReturnValue(createFakeMedia(false)),
    })
    expect(isDarkMode('auto')).toBe(false)
  })
})
