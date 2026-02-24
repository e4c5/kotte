import { useState, useRef, useEffect } from 'react'

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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.shiftKey || e.ctrlKey || e.metaKey) &&
        e.key === 'Enter' &&
        textareaRef.current === document.activeElement
      ) {
        e.preventDefault()
        onExecute()
        setExpanded(false)
      }

      if (e.key === 'Escape' && textareaRef.current === document.activeElement) {
        e.preventDefault()
        setExpanded(false)
        textareaRef.current?.blur()
      }

      if (e.ctrlKey || e.metaKey) {
        if (e.key === 'ArrowUp' && history.length > 0) {
          e.preventDefault()
          const newIndex = historyIndex < history.length - 1 ? historyIndex + 1 : historyIndex
          setHistoryIndex(newIndex)
          if (newIndex >= 0) {
            onChange(history[history.length - 1 - newIndex])
          }
        } else if (e.key === 'ArrowDown' && historyIndex >= 0) {
          e.preventDefault()
          const newIndex = historyIndex > 0 ? historyIndex - 1 : -1
          setHistoryIndex(newIndex)
          if (newIndex >= 0) {
            onChange(history[history.length - 1 - newIndex])
          } else {
            onChange('')
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [history, historyIndex, onChange, onExecute])

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
                  rows={3}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded text-zinc-100 font-mono text-xs resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
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
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
                  aria-label={loading ? 'Query is executing' : 'Execute query'}
                  aria-busy={loading}
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
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  showParams
                    ? 'bg-zinc-600 text-zinc-100'
                    : 'bg-zinc-700 hover:bg-zinc-600 text-zinc-400'
                }`}
                aria-label={showParams ? 'Hide parameters' : 'Show parameters'}
                aria-pressed={showParams}
              >
                Parameters {showParams ? '▼' : '{ }'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function getQueryParams(paramsString: string): Record<string, unknown> {
  try {
    return JSON.parse(paramsString)
  } catch {
    return {}
  }
}
