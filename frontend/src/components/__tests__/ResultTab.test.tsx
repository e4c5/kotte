import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultTab from '../ResultTab'
import type { QueryTab } from '../../stores/queryStore'

// jsdom doesn't ship ResizeObserver; ResultTab uses one for the canvas
// container. A minimal stub is enough for these tests since we mock GraphView.
beforeAll(() => {
  if (!('ResizeObserver' in globalThis)) {
    class ResizeObserverStub {
      observe(): void {
        /* no-op: jsdom test stub */
      }
      unobserve(): void {
        /* no-op: jsdom test stub */
      }
      disconnect(): void {
        /* no-op: jsdom test stub */
      }
    }
    const g = globalThis as unknown as { ResizeObserver: unknown }
    g.ResizeObserver = ResizeObserverStub
  }
})

// Mock heavy children — we only care about the banner / Graph-button gating
// driven by `vizDisabledReason` and `result.visualization_warning`.
vi.mock('../GraphView', () => ({
  default: () => <div data-testid="graphview-mock" />,
  // re-export type aliases used by ResultTab
}))
vi.mock('../TableView', () => ({
  default: () => <div data-testid="tableview-mock" />,
}))
vi.mock('../GraphControls', () => ({
  default: () => null,
}))
vi.mock('../NodeContextMenu', () => ({
  default: () => null,
}))
vi.mock('../../stores/graphStore', () => ({
  useGraphStore: (selector: (s: unknown) => unknown) =>
    selector({
      pinnedNodes: new Set<string>(),
      hiddenNodes: new Set<string>(),
      togglePinNode: vi.fn(),
      toggleHideNode: vi.fn(),
    }),
}))

function makeTab(overrides: Partial<QueryTab> = {}): QueryTab {
  return {
    id: 't1',
    name: 'Query 1',
    query: 'MATCH (n) RETURN n',
    params: '{}',
    graph: 'g1',
    result: {
      columns: ['n'],
      rows: [],
      row_count: 0,
      request_id: 'req1',
      graph_elements: { nodes: [{ id: '1', label: 'X' }], edges: [] },
    } as QueryTab['result'],
    loading: false,
    error: null,
    requestId: null,
    viewMode: 'table',
    pinned: false,
    createdAt: 0,
    lastActivity: 0,
    ...overrides,
  }
}

describe('ResultTab — viz limit enforcement (ROADMAP A5)', () => {
  it('renders the banner when vizDisabledReason is set', () => {
    render(
      <ResultTab
        tab={makeTab()}
        tablePageSize={50}
        vizDisabledReason="Result has 6,000 nodes, exceeding the visualization limit of 5,000."
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    const banner = screen.getByTestId('viz-unavailable-banner')
    expect(banner).toBeInTheDocument()
    expect(banner.textContent).toMatch(/Visualization unavailable/)
    expect(banner.textContent).toMatch(/6,000 nodes/)
  })

  it('disables the Graph View button when vizDisabledReason is set', () => {
    render(
      <ResultTab
        tab={makeTab()}
        tablePageSize={50}
        vizDisabledReason="too big"
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    const btn = screen.getByRole('button', { name: /switch to graph view/i })
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('title', 'too big')
  })

  it('exposes an Open Settings action when vizDisabledReason is client-side', async () => {
    const onOpenSettings = vi.fn()
    render(
      <ResultTab
        tab={makeTab()}
        tablePageSize={50}
        vizDisabledReason="too big"
        onOpenSettings={onOpenSettings}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /open settings/i }))
    expect(onOpenSettings).toHaveBeenCalledTimes(1)
  })

  it('does not show Open Settings when only the server visualization_warning is set', () => {
    const tab = makeTab({
      result: {
        ...makeTab().result!,
        visualization_warning: 'Server truncated the result',
      },
    })
    render(
      <ResultTab
        tab={tab}
        tablePageSize={50}
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    const banner = screen.getByTestId('viz-unavailable-banner')
    expect(banner.textContent).toMatch(/Server truncated the result/)
    expect(screen.queryByRole('button', { name: /open settings/i })).toBeNull()
  })

  it('hides Open Settings when the server warning preempts the client cap', () => {
    // Both reasons set simultaneously: the server warning wins (per the ?? in
    // vizUnavailableReason) so the banner shows the server message. Open
    // Settings would not fix that, so it must not appear.
    const tab = makeTab({
      result: {
        ...makeTab().result!,
        visualization_warning: 'Server truncated the result',
      },
    })
    render(
      <ResultTab
        tab={tab}
        tablePageSize={50}
        vizDisabledReason="Result has 6,000 nodes, exceeding the visualization limit of 5,000."
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    const banner = screen.getByTestId('viz-unavailable-banner')
    expect(banner.textContent).toMatch(/Server truncated the result/)
    expect(banner.textContent).not.toMatch(/6,000 nodes/)
    expect(screen.queryByRole('button', { name: /open settings/i })).toBeNull()
  })

  it('renders no banner when neither reason is present', () => {
    render(
      <ResultTab
        tab={makeTab()}
        tablePageSize={50}
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('viz-unavailable-banner')).toBeNull()
    expect(screen.getByRole('button', { name: /switch to graph view/i })).not.toBeDisabled()
  })
})

describe('ResultTab — isolate breadcrumb (ROADMAP A11.3)', () => {
  it('renders no breadcrumb when previousGraphElements is unset', () => {
    render(
      <ResultTab
        tab={makeTab()}
        tablePageSize={50}
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onRestoreFullResult={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('isolate-breadcrumb')).toBeNull()
  })

  it('renders the back-to-full-result breadcrumb when the tab holds a snapshot', () => {
    const tab = makeTab({
      // Any non-null snapshot is enough to flip the breadcrumb on; ResultTab
      // only checks truthiness of `tab.previousGraphElements`.
      previousGraphElements: {
        nodes: [{ id: 'a', label: 'X', properties: {}, type: 'node' }],
        edges: [],
      },
    })
    render(
      <ResultTab
        tab={tab}
        tablePageSize={50}
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onRestoreFullResult={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    const crumb = screen.getByTestId('isolate-breadcrumb')
    expect(crumb).toBeInTheDocument()
    expect(crumb.textContent).toMatch(/Back to full result/)
  })

  it('clicking the breadcrumb invokes onRestoreFullResult', async () => {
    const onRestoreFullResult = vi.fn()
    const tab = makeTab({
      previousGraphElements: {
        nodes: [{ id: 'a', label: 'X', properties: {}, type: 'node' }],
        edges: [],
      },
    })
    render(
      <ResultTab
        tab={tab}
        tablePageSize={50}
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onRestoreFullResult={onRestoreFullResult}
        onExportReady={vi.fn()}
      />,
    )
    await userEvent.click(
      screen.getByRole('button', { name: /back to full result/i }),
    )
    expect(onRestoreFullResult).toHaveBeenCalledTimes(1)
  })

  it('does not render the breadcrumb when onRestoreFullResult is not provided, even if a snapshot exists', () => {
    // Defensive: ResultTab guards rendering on both the snapshot AND the
    // handler, so omitting the handler hides the affordance entirely
    // (no dead button).
    const tab = makeTab({
      previousGraphElements: {
        nodes: [{ id: 'a', label: 'X', properties: {}, type: 'node' }],
        edges: [],
      },
    })
    render(
      <ResultTab
        tab={tab}
        tablePageSize={50}
        onOpenSettings={vi.fn()}
        onViewModeChange={vi.fn()}
        onNodeExpand={vi.fn()}
        onNodeDelete={vi.fn()}
        onExportReady={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('isolate-breadcrumb')).toBeNull()
  })
})
