import { useEffect } from 'react'

interface UseQueryEditorKeyboardOptions {
  /** Read latest history list (closure-stable read at event time). */
  history: string[]
  /** Current cursor position in the history stack (-1 = present input). */
  historyIndex: number
  /** True when the Cypher textarea owns focus. */
  isEditorFocused: () => boolean
  /** True when the JSON parameters textarea cannot be parsed. */
  paramsInvalid: boolean
  /**
   * True while a query is already in flight. Mirrors the Execute button's
   * `disabled` state so Shift/Ctrl/Meta+Enter cannot re-enter `onExecute`
   * (and double-submit) from the keyboard while the UI button is disabled.
   */
  loading: boolean
  /** Submit the current query. */
  onExecute: () => void
  /** Replace the query text (used by history stepping and Clear). */
  onChange: (value: string) => void
  /** Collapse / expand the editor chrome. */
  setExpanded: (expanded: boolean) => void
  /** Move the cursor through the history stack. */
  stepHistory: (direction: 'up' | 'down') => void
  /** Imperative ref to the textarea; used for blur on Escape. */
  blurEditor: () => void
}

/**
 * Global keyboard shortcuts for the QueryEditor.
 *
 * Extracted from the component body so the component itself stays under
 * SonarCloud's cognitive-complexity budget (rule typescript:S3776). The
 * deps array intentionally tracks the values the inner handler reads so
 * the latest closure runs on each event.
 */
export function useQueryEditorKeyboard({
  history,
  historyIndex,
  isEditorFocused,
  paramsInvalid,
  loading,
  onExecute,
  onChange,
  setExpanded,
  stepHistory,
  blurEditor,
}: UseQueryEditorKeyboardOptions): void {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isEditorFocused()) return

      if ((e.shiftKey || e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        // Mirror the Execute button's `disabled={loading || paramsInvalid}`
        // guard so keyboard shortcuts can't double-submit a query that's
        // already in flight or send params we know the backend will reject.
        if (loading || paramsInvalid) return
        onExecute()
        setExpanded(false)
        return
      }

      if (e.key === 'Escape') {
        e.preventDefault()
        setExpanded(false)
        blurEditor()
        return
      }

      if (!(e.ctrlKey || e.metaKey)) return

      if (e.key === 'ArrowUp') {
        e.preventDefault()
        stepHistory('up')
        return
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        stepHistory('down')
      }
    }

    globalThis.addEventListener('keydown', handleKeyDown)
    return () => globalThis.removeEventListener('keydown', handleKeyDown)
  }, [
    history,
    historyIndex,
    isEditorFocused,
    paramsInvalid,
    loading,
    onExecute,
    onChange,
    setExpanded,
    stepHistory,
    blurEditor,
  ])
}
