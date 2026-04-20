/**
 * useTheme — applies the persisted `settingsStore.theme` value to
 * `document.documentElement` so Tailwind's class-based `dark:` variant
 * (configured via `@custom-variant dark` in `index.css`) takes effect.
 *
 * Mount this once at the top of the React tree (see `App.tsx`). It is safe to
 * call from a component that re-renders frequently — the effect short-circuits
 * when the resolved class hasn't changed.
 *
 * Theme values:
 *   - 'dark'  → always add the `dark` class
 *   - 'light' → always remove it
 *   - 'auto'  → mirror `prefers-color-scheme: dark` and react to changes
 */

import { useEffect, useLayoutEffect } from 'react'
import { useSettingsStore, type Theme } from '../stores/settingsStore'

const DARK_CLASS = 'dark'

// Apply the theme class synchronously after DOM mutations but *before* the
// browser paints, so users with a persisted dark/auto theme never see a
// light-themed flash on initial load. Falls back to `useEffect` in non-DOM
// environments (SSR, tests without jsdom) to avoid React's
// "useLayoutEffect does nothing on the server" warning.
const useIsomorphicLayoutEffect =
  globalThis.window === undefined ? useEffect : useLayoutEffect

function applyDarkClass(isDark: boolean): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (isDark) {
    root.classList.add(DARK_CLASS)
  } else {
    root.classList.remove(DARK_CLASS)
  }
}

/**
 * Resolve the boolean "dark mode active" given a user-selected theme.
 * Exported for unit tests; treats `auto` by consulting `matchMedia`.
 */
export function isDarkMode(theme: Theme): boolean {
  if (theme === 'dark') return true
  if (theme === 'light') return false
  const win = globalThis.window
  if (win === undefined || typeof win.matchMedia !== 'function') {
    return false
  }
  return win.matchMedia('(prefers-color-scheme: dark)').matches
}

export function useTheme(): void {
  const theme = useSettingsStore((state) => state.theme)

  useIsomorphicLayoutEffect(() => {
    applyDarkClass(isDarkMode(theme))

    if (theme !== 'auto') {
      // Static theme — no need to listen for OS-level changes.
      return
    }
    const win = globalThis.window
    if (win === undefined || typeof win.matchMedia !== 'function') {
      return
    }

    const media = win.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent): void => {
      applyDarkClass(event.matches)
    }

    // Modern browsers expose addEventListener; older Safari only addListener.
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onChange)
      return () => media.removeEventListener('change', onChange)
    }
    // Safari < 14 only exposes the deprecated addListener/removeListener APIs;
    // they remain the only way to subscribe on those browsers.
    media.addListener(onChange) // NOSONAR: legacy Safari fallback (typescript:S1874)
    return () => media.removeListener(onChange) // NOSONAR: legacy Safari fallback (typescript:S1874)
  }, [theme])
}
