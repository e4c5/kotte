import { describe, it, expect, vi } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TabBar from '../TabBar'
import type { QueryTab } from '../../stores/queryStore'

function makeTab(overrides: Partial<QueryTab> & { id: string; name: string }): QueryTab {
  return {
    query: '',
    params: '{}',
    graph: null,
    result: null,
    loading: false,
    error: null,
    requestId: null,
    viewMode: 'table',
    pinned: false,
    createdAt: Date.now(),
    lastActivity: Date.now(),
    ...overrides,
  }
}

describe('TabBar', () => {
  const defaultTabs: QueryTab[] = [
    makeTab({ id: '1', name: 'Query 1', lastActivity: 100 }),
    makeTab({ id: '2', name: 'Query 2', lastActivity: 200 }),
  ]

  const defaultProps = {
    tabs: defaultTabs,
    activeTabId: '1',
    onTabClick: vi.fn(),
    onTabClose: vi.fn(),
    onNewTab: vi.fn(),
    onTabPin: vi.fn(),
    onTabUnpin: vi.fn(),
  }

  it('renders tablist with all tabs and new-tab button', () => {
    const { container } = render(<TabBar {...defaultProps} />)
    expect(screen.getByRole('tablist', { name: 'Query result tabs' })).toBeInTheDocument()
    expect(container.querySelector('#tab-1')).toBeInTheDocument()
    expect(container.querySelector('#tab-2')).toBeInTheDocument()
    expect(container.querySelector('button[title="New tab"]')).toBeInTheDocument()
  })

  it('marks active tab as selected', () => {
    const { container } = render(<TabBar {...defaultProps} activeTabId="2" />)
    const tab1 = container.querySelector('#tab-1')
    const tab2 = container.querySelector('#tab-2')
    expect(tab1).toHaveAttribute('aria-selected', 'false')
    expect(tab2).toHaveAttribute('aria-selected', 'true')
  })

  it('calls onTabClick when a tab is clicked', async () => {
    const user = userEvent.setup()
    const onTabClick = vi.fn()
    const { container } = render(<TabBar {...defaultProps} onTabClick={onTabClick} />)
    await user.click(container.querySelector('#tab-2')!)
    expect(onTabClick).toHaveBeenCalledWith('2')
  })

  it('calls onNewTab when new-tab button is clicked', async () => {
    const user = userEvent.setup()
    const onNewTab = vi.fn()
    const { container } = render(<TabBar {...defaultProps} onNewTab={onNewTab} />)
    const newTabBtn = container.querySelector('button[title="New tab"]') as HTMLButtonElement
    await user.click(newTabBtn)
    expect(onNewTab).toHaveBeenCalledTimes(1)
  })

  it('calls onTabClose when close button is clicked', async () => {
    const user = userEvent.setup()
    const onTabClose = vi.fn()
    const { container } = render(<TabBar {...defaultProps} onTabClose={onTabClose} />)
    const tab1 = container.querySelector('#tab-1')!
    const closeBtn = within(tab1 as HTMLElement).getByRole('button', { name: 'Close tab: Query 1' })
    await user.click(closeBtn)
    expect(onTabClose).toHaveBeenCalledWith('1', expect.any(Object))
  })

  it('calls onTabPin when pin button is clicked on unpinned tab', () => {
    const onTabPin = vi.fn()
    const { container } = render(<TabBar {...defaultProps} onTabPin={onTabPin} />)
    const tab1 = container.querySelector('#tab-1') as HTMLElement
    const pinBtn = within(tab1).getByRole('button', { name: 'Pin tab: Query 1' })
    fireEvent.click(pinBtn)
    expect(onTabPin).toHaveBeenCalledWith('1', expect.anything())
  })

  it('shows pinned indicator and unpin button for pinned tab', () => {
    const tabs = [makeTab({ id: '1', name: 'Pinned', pinned: true })]
    render(
      <TabBar
        {...defaultProps}
        tabs={tabs}
        activeTabId="1"
        onTabPin={vi.fn()}
        onTabUnpin={vi.fn()}
      />
    )
    expect(screen.getByLabelText('Pinned tab')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Unpin tab: Pinned' })).toBeInTheDocument()
  })

  it('calls onTabUnpin (not onTabPin) when pin button is clicked on pinned tab', () => {
    const onTabPin = vi.fn()
    const onTabUnpin = vi.fn()
    const tabs = [makeTab({ id: '1', name: 'Pinned', pinned: true })]
    const { container } = render(
      <TabBar
        {...defaultProps}
        tabs={tabs}
        activeTabId="1"
        onTabPin={onTabPin}
        onTabUnpin={onTabUnpin}
      />
    )
    const tab1 = container.querySelector('#tab-1') as HTMLElement
    const unpinBtn = within(tab1).getByRole('button', { name: 'Unpin tab: Pinned' })
    fireEvent.click(unpinBtn)
    expect(onTabUnpin).toHaveBeenCalledWith('1', expect.anything())
    expect(onTabPin).not.toHaveBeenCalled()
  })

  it('renders the pin button when only onTabUnpin is supplied and the tab is pinned', () => {
    const tabs = [makeTab({ id: '1', name: 'Pinned', pinned: true })]
    render(
      <TabBar
        {...defaultProps}
        tabs={tabs}
        activeTabId="1"
        onTabPin={undefined}
        onTabUnpin={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: 'Unpin tab: Pinned' })).toBeInTheDocument()
  })

  it('hides the pin button on unpinned tabs when only onTabUnpin is supplied', () => {
    const tabs = [makeTab({ id: '1', name: 'Unpinned', pinned: false })]
    render(
      <TabBar
        {...defaultProps}
        tabs={tabs}
        activeTabId="1"
        onTabPin={undefined}
        onTabUnpin={vi.fn()}
      />
    )
    expect(screen.queryByRole('button', { name: /Pin tab: / })).not.toBeInTheDocument()
  })

  it('hides the pin button on pinned tabs when only onTabPin is supplied', () => {
    const tabs = [makeTab({ id: '1', name: 'Pinned', pinned: true })]
    render(
      <TabBar
        {...defaultProps}
        tabs={tabs}
        activeTabId="1"
        onTabPin={vi.fn()}
        onTabUnpin={undefined}
      />
    )
    expect(screen.queryByRole('button', { name: /Unpin tab: / })).not.toBeInTheDocument()
  })

  it('shows loading indicator when tab is loading', () => {
    const tabs = [makeTab({ id: '1', name: 'Running', loading: true })]
    render(<TabBar {...defaultProps} tabs={tabs} activeTabId="1" />)
    expect(screen.getByLabelText('Query running')).toBeInTheDocument()
  })

  it('shows error indicator when tab has error', () => {
    const tabs = [makeTab({ id: '1', name: 'Failed', error: 'Syntax error' })]
    render(<TabBar {...defaultProps} tabs={tabs} activeTabId="1" />)
    expect(screen.getByLabelText('Error in query')).toBeInTheDocument()
  })
})
