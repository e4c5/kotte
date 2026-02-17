import type { QueryTab } from '../stores/queryStore'

interface TabBarProps {
  tabs: QueryTab[]
  activeTabId: string | null
  onTabClick: (tabId: string) => void
  onTabClose: (tabId: string, e: React.MouseEvent) => void
  onNewTab: () => void
  onTabPin: (tabId: string) => void
  onTabUnpin: (tabId: string) => void
}

export default function TabBar({
  tabs,
  activeTabId,
  onTabClick,
  onTabClose,
  onNewTab,
  onTabPin,
  onTabUnpin,
}: TabBarProps) {
  // Sort tabs: pinned first, then by last activity
  const sortedTabs = [...tabs].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1
    if (!a.pinned && b.pinned) return 1
    return b.lastActivity - a.lastActivity
  })

  return (
    <div
      role="tablist"
      aria-label="Query result tabs"
      style={{
        display: 'flex',
        borderBottom: '1px solid #ccc',
        backgroundColor: '#f5f5f5',
        overflowX: 'auto',
        alignItems: 'flex-end',
      }}
    >
      {sortedTabs.map((tab, index) => (
        <div
          key={tab.id}
          role="tab"
          aria-selected={activeTabId === tab.id}
          aria-controls={`tabpanel-${tab.id}`}
          id={`tab-${tab.id}`}
          tabIndex={activeTabId === tab.id ? 0 : -1}
          onClick={() => onTabClick(tab.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onTabClick(tab.id)
            } else if (e.key === 'ArrowLeft' && index > 0) {
              e.preventDefault()
              onTabClick(sortedTabs[index - 1].id)
            } else if (e.key === 'ArrowRight' && index < sortedTabs.length - 1) {
              e.preventDefault()
              onTabClick(sortedTabs[index + 1].id)
            } else if (e.key === 'Home') {
              e.preventDefault()
              onTabClick(sortedTabs[0].id)
            } else if (e.key === 'End') {
              e.preventDefault()
              onTabClick(sortedTabs[sortedTabs.length - 1].id)
            }
          }}
          style={{
            padding: '0.5rem 1rem',
            borderRight: '1px solid #ccc',
            borderTop: '1px solid #ccc',
            borderTopLeftRadius: '4px',
            borderTopRightRadius: '4px',
            backgroundColor: activeTabId === tab.id ? 'white' : '#e9e9e9',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            minWidth: '150px',
            maxWidth: '250px',
            position: 'relative',
            marginRight: '2px',
            borderBottom: activeTabId === tab.id ? 'none' : '1px solid #ccc',
            outline: 'none',
          }}
          title={tab.name}
        >
          {tab.pinned && (
            <span style={{ fontSize: '0.8rem' }} aria-label="Pinned tab" role="img">📌</span>
          )}
          <span
            style={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontSize: '0.9rem',
            }}
          >
            {tab.name}
          </span>
          {tab.loading && (
            <span style={{ fontSize: '0.8rem' }} aria-label="Query running" role="status">⏳</span>
          )}
          {tab.error && (
            <span style={{ fontSize: '0.8rem', color: '#dc3545' }} aria-label="Error in query" role="alert">⚠️</span>
          )}
          <div
            style={{
              display: 'flex',
              gap: '0.25rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {!tab.pinned && (
              <button
                onClick={() => onTabPin(tab.id)}
                aria-label={`Pin tab: ${tab.name}`}
                style={{
                  padding: '0.125rem 0.25rem',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                }}
                title="Pin tab"
              >
                📌
              </button>
            )}
            {tab.pinned && (
              <button
                onClick={() => onTabUnpin(tab.id)}
                aria-label={`Unpin tab: ${tab.name}`}
                style={{
                  padding: '0.125rem 0.25rem',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                }}
                title="Unpin tab"
              >
                📍
              </button>
            )}
            <button
              onClick={(e) => onTabClose(tab.id, e)}
              aria-label={`Close tab: ${tab.name}`}
              style={{
                padding: '0.125rem 0.25rem',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                fontSize: '0.9rem',
                borderRadius: '2px',
              }}
              title="Close tab"
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#ffcccc'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent'
              }}
            >
              ×
            </button>
          </div>
        </div>
      ))}
      <button
        onClick={onNewTab}
        aria-label="Create new query tab"
        style={{
          padding: '0.5rem 1rem',
          border: 'none',
          borderBottom: '1px solid #ccc',
          backgroundColor: 'transparent',
          cursor: 'pointer',
          fontSize: '1.2rem',
          marginLeft: 'auto',
        }}
        title="New tab"
      >
        +
      </button>
    </div>
  )
}

