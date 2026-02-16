import { useEffect, useRef } from 'react'

export interface NodeContextMenuProps {
  x: number
  y: number
  nodeId: string
  onExpand?: (nodeId: string) => void
  onDelete?: (nodeId: string) => void
  onClose: () => void
}

export default function NodeContextMenu({
  x,
  y,
  nodeId,
  onExpand,
  onDelete,
  onClose,
}: NodeContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose()
      }
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [onClose])

  const handleExpand = () => {
    onExpand?.(nodeId)
    onClose()
  }

  const handleDelete = () => {
    if (onDelete) {
      onDelete(nodeId)
    }
    onClose()
  }

  return (
    <div
      ref={menuRef}
      style={{
        position: 'fixed',
        left: `${x}px`,
        top: `${y}px`,
        backgroundColor: 'white',
        border: '1px solid #ccc',
        borderRadius: '4px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        minWidth: '150px',
        padding: '4px 0',
      }}
    >
      {onExpand && (
        <button
          onClick={handleExpand}
          style={{
            width: '100%',
            padding: '8px 16px',
            textAlign: 'left',
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontSize: '14px',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#f0f0f0'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          Expand Neighborhood
        </button>
      )}
      {onDelete && (
        <button
          onClick={handleDelete}
          style={{
            width: '100%',
            padding: '8px 16px',
            textAlign: 'left',
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontSize: '14px',
            color: '#dc3545',
            borderTop: onExpand ? '1px solid #eee' : 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#fff5f5'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          Delete Node
        </button>
      )}
    </div>
  )
}

