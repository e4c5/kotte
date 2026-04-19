import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useQueryEditorKeyboard } from '../hooks/useQueryEditorKeyboard'

interface QueryEditorProps {
  value: string
  onChange: (value: string) => void
  params?: string
  onParamsChange?: (value: string) => void
  onExecute: () => void
  onCancel?: () => void
  loading?: boolean
  history?: string[]
}

function pickExecuteAriaLabel(loading: boolean, paramsInvalid: boolean): string {
  if (loading) return 'Query is executing'
  if (paramsInvalid) return 'Execute query (disabled: parameters JSON is invalid)'
  return 'Execute query'
}

function pickParamsToggleAriaLabel(showParams: boolean, paramsInvalid: boolean): string {
  if (showParams) return 'Hide parameters'
  if (paramsInvalid) return 'Show parameters (parameters JSON is invalid)'
  return 'Show parameters'
}

export default function QueryEditor({
  value,
  onChange,
  params: controlledParams = '{}',
  onParamsChange,
  onExecute,
  onCancel,
  loading = false,
  history = [],
}: QueryEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [expanded, setExpanded] = useState(false)
  const [showParams, setShowParams] = useState(false)
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [localParams, setLocalParams] = useState(() => controlledParams)

  const params = onParamsChange !== undefined ? controlledParams : localParams
  const setParams = onParamsChange ?? setLocalParams

  const paramsResult = useMemo(() => getQueryParams(params), [params])
  const paramsInvalid = !paramsResult.ok
  const paramsErrorMessage = paramsResult.ok ? null : paramsResult.error

  const isEditorFocused = useCallback(
    () => textareaRef.current === document.activeElement,
    []
  )
  const blurEditor = useCallback(() => textareaRef.current?.blur(), [])

  const applyHistoryAtIndex = (index: number) => {
    if (index >= 0) {
      onChange(history[history.length - 1 - index])
      return
    }
    onChange('')
  }

  const stepHistory = useCallback(
    (direction: 'up' | 'down') => {
      if (direction === 'up') {
        if (history.length === 0) return
        const newIndex = historyIndex < history.length - 1 ? historyIndex + 1 : historyIndex
        setHistoryIndex(newIndex)
        applyHistoryAtIndex(newIndex)
        return
      }

      if (historyIndex < 0) return
      const newIndex = historyIndex > 0 ? historyIndex - 1 : -1
      setHistoryIndex(newIndex)
      applyHistoryAtIndex(newIndex)
    },
    // applyHistoryAtIndex closes over `history` and `onChange`; tracking
    // those keeps the callback stable for the keyboard hook below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [history, historyIndex, onChange]
  )

  useQueryEditorKeyboard({
    history,
    historyIndex,
    isEditorFocused,
    paramsInvalid,
    onExecute,
    onChange,
    setExpanded,
    stepHistory,
    blurEditor,
  })

  useEffect(() => {
    if (!expanded) return
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setExpanded(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [expanded])

  const handleParamsChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setParams(e.target.value)
  }

  const executeAriaLabel = pickExecuteAriaLabel(loading, paramsInvalid)
  const paramsToggleAriaLabel = pickParamsToggleAriaLabel(showParams, paramsInvalid)
  const paramsToggleTitle =
    paramsInvalid && !showParams
      ? 'Parameters JSON is invalid \u2014 click to view error'
      : undefined

  return (
    <div ref={containerRef} className="relative w-full">
      <div
        className={`bg-zinc-950 border-y border-zinc-800 overflow-hidden ${
          expanded ? 'shadow-xl border border-zinc-700 ring-2 ring-blue-500/50' : ''
        }`}
      >
        <div className={`flex items-center gap-2 px-4 ${expanded ? 'py-2 border-b border-zinc-700' : 'h-full'}`}>
          <span className="text-zinc-500" aria-hidden="true">⌕</span>
          <label htmlFor="cypher-query" className="sr-only">Cypher query</label>
          <textarea
            id="cypher-query"
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onFocus={() => setExpanded(true)}
            placeholder="Enter Cypher Query... (Shift+Enter to run)"
            aria-label="Cypher query editor"
            rows={expanded ? 6 : 1}
            className={`flex-1 min-w-0 bg-transparent text-zinc-100 placeholder-zinc-500 font-mono text-sm resize-none focus:outline-none ${
              expanded ? 'py-1' : 'py-0'
            }`}
          />
        </div>

        {expanded && (
          <>
            {showParams && (
              <div className="border-t border-zinc-700 p-3">
                <label htmlFor="query-params" className="block text-xs font-medium text-zinc-400 mb-1">
                  Parameters (JSON)
                </label>
                <textarea
                  id="query-params"
                  value={params}
                  onChange={handleParamsChange}
                  placeholder='{"name": "Alice"}'
                  aria-label="Query parameters"
                  aria-invalid={paramsInvalid}
                  aria-describedby={paramsInvalid ? 'query-params-error' : undefined}
                  rows={3}
                  className={`w-full px-3 py-2 bg-zinc-900 border rounded text-zinc-100 font-mono text-xs resize-none focus:outline-none focus:ring-2 ${
                    paramsInvalid
                      ? 'border-red-500 focus:ring-red-500'
                      : 'border-zinc-600 focus:ring-blue-500'
                  }`}
                />
                {paramsInvalid && (
                  <p
                    id="query-params-error"
                    role="alert"
                    className="mt-1 text-xs text-red-400 font-mono"
                  >
                    {paramsErrorMessage}
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center gap-2 px-3 py-2 border-t border-zinc-700 bg-zinc-800/80">
              {loading && onCancel ? (
                <button
                  type="button"
                  onClick={onCancel}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors"
                  aria-label="Cancel running query"
                >
                  Cancel
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    onExecute()
                    setExpanded(false)
                  }}
                  disabled={loading || paramsInvalid}
                  title={paramsInvalid ? 'Fix the invalid JSON in Parameters to enable Execute' : undefined}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
                  aria-label={executeAriaLabel}
                  aria-busy={loading}
                  aria-disabled={loading || paramsInvalid}
                >
                  <span aria-hidden="true">▶</span>
                  {loading ? 'Executing...' : 'Execute'}
                </button>
              )}
              <button
                type="button"
                onClick={() => onChange('')}
                disabled={loading}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-600 hover:bg-zinc-500 text-zinc-200 text-sm font-medium transition-colors"
                aria-label="Clear query"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => setShowParams(!showParams)}
                className={`relative inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  showParams
                    ? 'bg-zinc-600 text-zinc-100'
                    : 'bg-zinc-700 hover:bg-zinc-600 text-zinc-400'
                }`}
                aria-label={paramsToggleAriaLabel}
                aria-pressed={showParams}
                title={paramsToggleTitle}
              >
                Parameters {showParams ? '▼' : '{ }'}
                {paramsInvalid && !showParams && (
                  <span
                    aria-hidden="true"
                    data-testid="params-invalid-dot"
                    className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-red-500 ring-2 ring-zinc-800"
                  />
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export type QueryParamsResult =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; error: string }

/**
 * Parse the contents of the parameters textarea.
 *
 * Returns a discriminated union so the editor can:
 *   - keep the Execute button enabled / disabled in lock-step with validity,
 *   - render an inline error caption under the textarea,
 *   - and refuse to fire onExecute via Shift+Enter when params are unparseable.
 *
 * We deliberately do _not_ deep-validate the shape of individual parameter
 * values, but we DO enforce that the top-level value is a plain JSON object
 * (`{...}`), because the backend contract is `params: Optional[Dict[str, Any]]`
 * (see `backend/app/models/query.py`). Without this guard, syntactically valid
 * but non-object JSON like `[]`, `null`, `42`, or `"text"` would parse cleanly
 * here, enable Execute, and then 422 at the API instead of failing fast in the
 * editor. The historical "swallow the error and silently send {}" behaviour is
 * gone.
 */
export function getQueryParams(paramsString: string): QueryParamsResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(paramsString)
  } catch (err) {
    const detail = err instanceof Error ? err.message : 'unable to parse'
    return { ok: false, error: `Invalid JSON: ${detail}` }
  }

  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, error: 'Parameters must be a JSON object' }
  }

  return { ok: true, value: parsed as Record<string, unknown> }
}
