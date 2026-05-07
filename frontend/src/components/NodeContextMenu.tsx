import { useEffect, useRef } from 'react'

export interface NodeContextMenuProps {
  x: number
  y: number
  nodeId: string
  /**
   * Legacy single-step expand (no options). Kept for backwards compatibility;
   * prefer `onExpandOptions` when the popover is available.
   */
  onExpand?: (nodeId: string) => void
  /**
   * ROADMAP C7 — opens the ExpandOptionsPopover at (x, y) so the user can
   * configure depth, direction, limit, and relationship-type filters before
   * expanding. When present, this replaces the direct `onExpand` call.
   */
  onExpandOptions?: (nodeId: string, x: number, y: number) => void
  onDelete?: (nodeId: string) => void
  onPin?: (nodeId: string) => void
  onHide?: (nodeId: string) => void
  /**
   * ROADMAP A11 phase 3 — wires the explicit "show only this node and its
   * neighbourhood" gesture. The action is destructive on the canvas but
   * reversible via the breadcrumb that ResultTab renders while the snapshot
   * is held.
   */
  onIsolateNeighborhood?: (nodeId: string) => void
  isPinned?: boolean
  isHidden?: boolean
  onClose: () => void
}

export default function NodeContextMenu({
  x,
  y,
  nodeId,
  onExpand,
  onExpandOptions,
  onDelete,
  onPin,
  onHide,
  onIsolateNeighborhood,
  isPinned = false,
  isHidden = false,
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
    if (onExpandOptions) {
      // Open the options popover; the caller manages closing the menu.
      onExpandOptions(nodeId, x, y)
      onClose()
    } else {
      onExpand?.(nodeId)
      onClose()
    }
  }

  const handleDelete = () => {
    if (onDelete) {
      onDelete(nodeId)
    }
    onClose()
  }

  const handlePin = () => {
    onPin?.(nodeId)
    onClose()
  }

  const handleHide = () => {
    onHide?.(nodeId)
    onClose()
  }

  const handleIsolate = () => {
    onIsolateNeighborhood?.(nodeId)
    onClose()
  }

  const pinLabel = isPinned ? 'Unpin Node' : 'Pin Node'
  const hideLabel = isHidden ? 'Show Node' : 'Hide Node'

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
      {(onExpand || onExpandOptions) && (
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
          Expand Neighborhood{onExpandOptions ? ' ▸' : ''}
        </button>
      )}
      {onPin && (
        <button
          onClick={handlePin}
          role="menuitemcheckbox"
          aria-label={`${pinLabel} ${nodeId}`}
          aria-checked={isPinned}
          style={{
            width: '100%',
            padding: '8px 16px',
            textAlign: 'left',
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontSize: '14px',
            borderTop: (onExpand || onExpandOptions) ? '1px solid #eee' : 'none',
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
          {pinLabel}
        </button>
      )}
      {onHide && (
        <button
          onClick={handleHide}
          role="menuitemcheckbox"
          aria-label={`${hideLabel} ${nodeId}`}
          aria-checked={isHidden}
          style={{
            width: '100%',
            padding: '8px 16px',
            textAlign: 'left',
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontSize: '14px',
            borderTop: (onExpand || onPin) ? '1px solid #eee' : 'none',
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
          {hideLabel}
        </button>
      )}
      {onIsolateNeighborhood && (
        <button
          onClick={handleIsolate}
          role="menuitem"
          aria-label={`Show only node ${nodeId} and its neighbourhood`}
          style={{
            width: '100%',
            padding: '8px 16px',
            textAlign: 'left',
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontSize: '14px',
            borderTop: (onExpand || onPin || onHide) ? '1px solid #eee' : 'none',
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
          Show only this & its neighbourhood
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
            borderTop: (onExpand || onPin || onHide || onIsolateNeighborhood) ? '1px solid #eee' : 'none',
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
