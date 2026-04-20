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

import { useEffect } from 'react'
import { useSettingsStore, type Theme } from '../stores/settingsStore'

const DARK_CLASS = 'dark'

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
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function useTheme(): void {
  const theme = useSettingsStore((state) => state.theme)

  useEffect(() => {
    applyDarkClass(isDarkMode(theme))

    if (theme !== 'auto') {
      // Static theme — no need to listen for OS-level changes.
      return
    }
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return
    }

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent): void => {
      applyDarkClass(event.matches)
    }

    // Modern browsers expose addEventListener; older Safari only addListener.
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onChange)
      return () => media.removeEventListener('change', onChange)
    }
    media.addListener(onChange)
    return () => media.removeListener(onChange)
  }, [theme])
}
