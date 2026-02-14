import { useState, useRef, useEffect } from 'react'

interface QueryEditorProps {
  value: string
  onChange: (value: string) => void
  onExecute: () => void
  history?: string[]
}

export default function QueryEditor({
  value,
  onChange,
  onExecute,
  history = [],
}: QueryEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [params, setParams] = useState('{}')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Execute on Shift+Enter or Ctrl+Enter
      if (
        (e.shiftKey || e.ctrlKey || e.metaKey) &&
        e.key === 'Enter' &&
        textareaRef.current === document.activeElement
      ) {
        e.preventDefault()
        onExecute()
      }

      // History navigation with Ctrl+Up/Down
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

  const handleParamsChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setParams(e.target.value)
    try {
      JSON.parse(e.target.value)
    } catch {
      // Invalid JSON, but allow editing
    }
  }

  const getParams = (): Record<string, unknown> => {
    try {
      return JSON.parse(params)
    } catch {
      return {}
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: '1rem', flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <label style={{ marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Cypher Query
          </label>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="MATCH (n) RETURN n LIMIT 10"
            style={{
              flex: 1,
              fontFamily: 'monospace',
              padding: '0.75rem',
              fontSize: '14px',
              border: '1px solid #ccc',
              borderRadius: '4px',
              resize: 'none',
            }}
          />
          <div style={{ marginTop: '0.5rem', fontSize: '12px', color: '#666' }}>
            Shift+Enter or Ctrl+Enter to execute • Ctrl+Up/Down for history
          </div>
        </div>
        <div style={{ width: '300px', display: 'flex', flexDirection: 'column' }}>
          <label style={{ marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Parameters (JSON)
          </label>
          <textarea
            value={params}
            onChange={handleParamsChange}
            placeholder='{"name": "Alice"}'
            style={{
              flex: 1,
              fontFamily: 'monospace',
              padding: '0.75rem',
              fontSize: '12px',
              border: '1px solid #ccc',
              borderRadius: '4px',
              resize: 'none',
            }}
          />
        </div>
      </div>
      <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
        <button
          onClick={onExecute}
          style={{
            padding: '0.5rem 1.5rem',
            fontSize: '1rem',
            cursor: 'pointer',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
          }}
        >
          Execute Query
        </button>
        <button
          onClick={() => onChange('')}
          style={{
            padding: '0.5rem 1.5rem',
            fontSize: '1rem',
            cursor: 'pointer',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
          }}
        >
          Clear
        </button>
      </div>
    </div>
  )
}

// Export helper to get params
export function getQueryParams(paramsString: string): Record<string, unknown> {
  try {
    return JSON.parse(paramsString)
  } catch {
    return {}
  }
}

