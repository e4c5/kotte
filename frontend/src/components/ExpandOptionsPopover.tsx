import { useEffect, useRef, useState } from 'react'

export interface ExpandOptions {
  depth: number
  limit: number
  edge_labels: string[] | undefined
  direction: 'in' | 'out' | 'both'
}

export interface ExpandOptionsPopoverProps {
  x: number
  y: number
  nodeId: string
  /** Available relationship types from graph metadata. */
  availableEdgeLabels: string[]
  /** Called when the user clicks "Expand". */
  onExpand: (nodeId: string, options: ExpandOptions) => void
  onClose: () => void
}

const DIRECTIONS: { value: 'in' | 'out' | 'both'; label: string }[] = [
  { value: 'both', label: '↔ Both' },
  { value: 'out', label: '→ Outgoing' },
  { value: 'in', label: '← Incoming' },
]

export default function ExpandOptionsPopover({
  x,
  y,
  nodeId,
  availableEdgeLabels,
  onExpand,
  onClose,
}: ExpandOptionsPopoverProps) {
  const popoverRef = useRef<HTMLDialogElement>(null)
  const [depth, setDepth] = useState(1)
  const [limit, setLimit] = useState(100)
  const [direction, setDirection] = useState<'in' | 'out' | 'both'>('both')
  // null = all types selected; string[] = explicit subset
  const [selectedLabels, setSelectedLabels] = useState<string[] | null>(null)

  useEffect(() => {
    const onMouseDown = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose])

  useEffect(() => {
    popoverRef.current?.querySelector('button')?.focus()
  }, [])

  // Keep popover on screen
  const popoverWidth = 280
  const popoverMaxHeight = 420
  const adjustedX = Math.min(x, window.innerWidth - popoverWidth - 8)
  const adjustedY = Math.min(y, window.innerHeight - popoverMaxHeight - 8)

  const toggleLabel = (label: string) => {
    if (selectedLabels === null) {
      // "All" was selected — switch to explicit selection excluding this label
      setSelectedLabels(availableEdgeLabels.filter((l) => l !== label))
    } else if (selectedLabels.includes(label)) {
      const next = selectedLabels.filter((l) => l !== label)
      setSelectedLabels(next.length === 0 ? null : next)
    } else {
      const next = [...selectedLabels, label]
      setSelectedLabels(next.length === availableEdgeLabels.length ? null : next)
    }
  }

  const isLabelSelected = (label: string) =>
    selectedLabels === null || selectedLabels.includes(label)

  const handleExpand = () => {
    const options: ExpandOptions = {
      depth,
      limit,
      direction,
      edge_labels: selectedLabels ?? undefined,
    }
    onExpand(nodeId, options)
    onClose()
  }

  return (
    <dialog
      ref={popoverRef}
      open
      aria-label={`Expand options for node ${nodeId}`}
      style={{
        position: 'fixed',
        left: adjustedX,
        top: adjustedY,
        width: popoverWidth,
        backgroundColor: 'white',
        border: '1px solid #ccc',
        borderRadius: '6px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
        zIndex: 1100,
        padding: '12px 14px',
        fontSize: '13px',
        outline: 'none',
        margin: 0,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 10, fontSize: '14px' }}>
        Expand Neighbourhood
      </div>

      {/* Direction */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ color: '#555', marginBottom: 4 }}>Direction</div>
        <div style={{ display: 'flex', gap: 4 }}>
          {DIRECTIONS.map((d) => (
            <button
              key={d.value}
              onClick={() => setDirection(d.value)}
              style={{
                flex: 1,
                padding: '4px 0',
                border: '1px solid',
                borderColor: direction === d.value ? '#4f46e5' : '#d1d5db',
                borderRadius: 4,
                backgroundColor: direction === d.value ? '#eef2ff' : 'white',
                color: direction === d.value ? '#4f46e5' : '#374151',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: direction === d.value ? 600 : 400,
              }}
              aria-pressed={direction === d.value}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      {/* Depth */}
      <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: '#555', minWidth: 40 }}>Depth</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {[1, 2].map((d) => (
            <button
              key={d}
              onClick={() => setDepth(d)}
              style={{
                width: 32,
                height: 28,
                border: '1px solid',
                borderColor: depth === d ? '#4f46e5' : '#d1d5db',
                borderRadius: 4,
                backgroundColor: depth === d ? '#eef2ff' : 'white',
                color: depth === d ? '#4f46e5' : '#374151',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: depth === d ? 600 : 400,
              }}
              aria-pressed={depth === d}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Limit */}
      <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        <label htmlFor="expand-limit" style={{ color: '#555', minWidth: 40 }}>
          Limit
        </label>
        <input
          id="expand-limit"
          type="number"
          min={1}
          max={1000}
          value={limit}
          onChange={(e) => setLimit(Math.min(1000, Math.max(1, Number(e.target.value))))}
          style={{
            width: 70,
            padding: '3px 6px',
            border: '1px solid #d1d5db',
            borderRadius: 4,
            fontSize: '13px',
          }}
        />
      </div>

      {/* Relationship types */}
      {availableEdgeLabels.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ color: '#555', marginBottom: 4 }}>
            Relationship types
            {selectedLabels !== null && (
              <button
                onClick={() => setSelectedLabels(null)}
                style={{
                  marginLeft: 6,
                  fontSize: '11px',
                  color: '#4f46e5',
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  textDecoration: 'underline',
                }}
              >
                select all
              </button>
            )}
          </div>
          <div
            style={{
              maxHeight: 120,
              overflowY: 'auto',
              border: '1px solid #e5e7eb',
              borderRadius: 4,
              padding: '4px 0',
            }}
          >
            {availableEdgeLabels.map((label) => (
              <label
                key={label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '3px 8px',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={isLabelSelected(label)}
                  onChange={() => toggleLabel(label)}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ fontSize: '12px', color: '#374151' }}>{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button
          onClick={onClose}
          style={{
            padding: '5px 12px',
            border: '1px solid #d1d5db',
            borderRadius: 4,
            backgroundColor: 'white',
            color: '#374151',
            cursor: 'pointer',
            fontSize: '13px',
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleExpand}
          style={{
            padding: '5px 12px',
            border: 'none',
            borderRadius: 4,
            backgroundColor: '#4f46e5',
            color: 'white',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          Expand
        </button>
      </div>
    </dialog>
  )
}
