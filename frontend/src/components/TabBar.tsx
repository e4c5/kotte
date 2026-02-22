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
  const sortedTabs = [...tabs].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1
    if (!a.pinned && b.pinned) return 1
    return b.lastActivity - a.lastActivity
  })

  return (
    <div
      role="tablist"
      aria-label="Query result tabs"
      className="flex overflow-x-auto items-center gap-0.5 min-w-0"
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
          className={`
            flex items-center gap-1.5 px-2.5 py-1.5 rounded-t text-sm cursor-pointer outline-none
            min-w-0 max-w-[180px] shrink-0
            transition-colors
            ${activeTabId === tab.id
              ? 'bg-zinc-700 text-zinc-100'
              : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
            }
          `}
          title={tab.name}
        >
          {tab.pinned && (
            <span className="text-xs shrink-0" aria-label="Pinned tab" role="img">📌</span>
          )}
          <span className="flex-1 truncate">{tab.name}</span>
          {tab.loading && (
            <span className="text-xs shrink-0" aria-label="Query running" role="status">⏳</span>
          )}
          {tab.error && (
            <span className="text-xs shrink-0 text-red-400" aria-label="Error in query" role="alert">⚠️</span>
          )}
          <div className="flex items-center gap-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
            {!tab.pinned && (
              <button
                type="button"
                onClick={() => onTabPin(tab.id)}
                aria-label={`Pin tab: ${tab.name}`}
                className="p-0.5 rounded hover:bg-zinc-600 text-zinc-400 hover:text-zinc-200 text-xs"
                title="Pin tab"
              >
                📌
              </button>
            )}
            {tab.pinned && (
              <button
                type="button"
                onClick={() => onTabUnpin(tab.id)}
                aria-label={`Unpin tab: ${tab.name}`}
                className="p-0.5 rounded hover:bg-zinc-600 text-zinc-400 hover:text-zinc-200 text-xs"
                title="Unpin tab"
              >
                📍
              </button>
            )}
            <button
              type="button"
              onClick={(e) => onTabClose(tab.id, e)}
              aria-label={`Close tab: ${tab.name}`}
              className="p-0.5 rounded hover:bg-red-900/50 text-zinc-400 hover:text-red-300 text-sm leading-none"
              title="Close tab"
            >
              ×
            </button>
          </div>
        </div>
      ))}
      <button
        type="button"
        onClick={onNewTab}
        aria-label="Create new query tab"
        className="shrink-0 px-2 py-1.5 rounded text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 text-lg leading-none transition-colors"
        title="New tab"
      >
        +
      </button>
    </div>
  )
}
