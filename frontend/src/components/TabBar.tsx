import type { QueryTab } from '../stores/queryStore'

interface TabBarProps {
  tabs: QueryTab[]
  activeTabId: string | null
  onTabClick: (tabId: string) => void
  onTabClose: (tabId: string, e: React.MouseEvent) => void
  onNewTab: () => void
}

export default function TabBar({
  tabs,
  activeTabId,
  onTabClick,
  onTabClose,
  onNewTab,
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
      className="flex items-end gap-1 min-w-0 h-9 px-1"
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
            flex items-center gap-1.5 px-3 py-1 text-sm cursor-pointer outline-none
            min-w-0 max-w-[180px] shrink-0 h-8
            transition-colors border
            ${activeTabId === tab.id
              ? 'bg-zinc-900 text-zinc-100 border-zinc-600 border-b-zinc-900 rounded-t-md'
              : 'bg-zinc-900/40 text-zinc-400 border-transparent hover:text-zinc-100 hover:border-zinc-600 hover:bg-zinc-900/70 rounded-t-md'
            }
          `}
          title={tab.name}
        >
          <span className="flex-1 truncate">{tab.name}</span>
          <div className="flex items-center gap-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={(e) => onTabClose(tab.id, e)}
              aria-label={`Close tab: ${tab.name}`}
              className="p-0.5 rounded text-zinc-400 text-sm leading-none"
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
        className="shrink-0 h-8 w-8 flex items-center justify-center cursor-pointer outline-none rounded-t-md text-sm leading-none text-zinc-400 bg-zinc-900/40 border border-transparent hover:text-zinc-100 hover:border-zinc-600 hover:bg-zinc-900/70 transition-colors"
        title="New tab"
      >
        +
      </button>
    </div>
  )
}
