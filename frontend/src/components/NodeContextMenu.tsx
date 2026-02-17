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

  useEffect(() => {
    // Focus first button when menu opens
    if (menuRef.current) {
      const firstButton = menuRef.current.querySelector('button') as HTMLButtonElement
      if (firstButton) {
        firstButton.focus()
      }
    }
  }, [])

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="Node actions menu"
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
        outline: 'none',
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          onClose()
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault()
          const buttons = Array.from(menuRef.current?.querySelectorAll('button') || []) as HTMLButtonElement[]
          const currentButton = e.target as HTMLButtonElement
          const currentIndex = buttons.indexOf(currentButton)
          if (currentIndex >= 0) {
            if (e.key === 'ArrowDown') {
              const nextIndex = currentIndex < buttons.length - 1 ? currentIndex + 1 : 0
              buttons[nextIndex]?.focus()
            } else {
              const prevIndex = currentIndex > 0 ? currentIndex - 1 : buttons.length - 1
              buttons[prevIndex]?.focus()
            }
          }
        }
      }}
    >
      {onExpand && (
        <button
          onClick={handleExpand}
          role="menuitem"
          aria-label={`Expand neighborhood for node ${nodeId}`}
          style={{
            width: '100%',
            padding: '8px 16px',
            textAlign: 'left',
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontSize: '14px',
            outline: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#f0f0f0'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
          onFocus={(e) => {
            e.currentTarget.style.backgroundColor = '#f0f0f0'
          }}
          onBlur={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          Expand Neighborhood
        </button>
      )}
      {onDelete && (
        <button
          onClick={handleDelete}
          role="menuitem"
          aria-label={`Delete node ${nodeId}`}
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
            outline: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#fff5f5'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
          onFocus={(e) => {
            e.currentTarget.style.backgroundColor = '#fff5f5'
          }}
          onBlur={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          Delete Node
        </button>
      )}
    </div>
  )
}

