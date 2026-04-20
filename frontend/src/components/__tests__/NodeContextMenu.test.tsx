import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NodeContextMenu from '../NodeContextMenu'

describe('NodeContextMenu — Pin/Hide actions (ROADMAP A3)', () => {
  const baseProps = {
    x: 100,
    y: 100,
    nodeId: 'node-42',
    onClose: vi.fn(),
  }

  it('renders Pin Node when onPin is provided and node is not pinned', () => {
    render(<NodeContextMenu {...baseProps} onPin={vi.fn()} isPinned={false} />)
    const btn = screen.getByRole('menuitemcheckbox', { name: /Pin Node node-42/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-checked', 'false')
  })

  it('renders Unpin Node when isPinned=true', () => {
    render(<NodeContextMenu {...baseProps} onPin={vi.fn()} isPinned={true} />)
    const btn = screen.getByRole('menuitemcheckbox', { name: /Unpin Node node-42/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-checked', 'true')
  })

  it('renders Hide Node when onHide is provided and node is not hidden', () => {
    render(<NodeContextMenu {...baseProps} onHide={vi.fn()} isHidden={false} />)
    expect(
      screen.getByRole('menuitemcheckbox', { name: /Hide Node node-42/i }),
    ).toBeInTheDocument()
  })

  it('renders Show Node when isHidden=true', () => {
    render(<NodeContextMenu {...baseProps} onHide={vi.fn()} isHidden={true} />)
    expect(
      screen.getByRole('menuitemcheckbox', { name: /Show Node node-42/i }),
    ).toBeInTheDocument()
  })

  it('omits Pin/Hide buttons when handlers are not provided', () => {
    render(<NodeContextMenu {...baseProps} onExpand={vi.fn()} />)
    expect(screen.queryByRole('menuitemcheckbox', { name: /Pin Node/i })).toBeNull()
    expect(screen.queryByRole('menuitemcheckbox', { name: /Hide Node/i })).toBeNull()
  })

  it('invokes onPin with the nodeId and closes the menu', async () => {
    const onPin = vi.fn()
    const onClose = vi.fn()
    render(
      <NodeContextMenu
        {...baseProps}
        onClose={onClose}
        onPin={onPin}
        isPinned={false}
      />,
    )
    await userEvent.click(
      screen.getByRole('menuitemcheckbox', { name: /Pin Node node-42/i }),
    )
    expect(onPin).toHaveBeenCalledTimes(1)
    expect(onPin).toHaveBeenCalledWith('node-42')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('invokes onHide with the nodeId and closes the menu', async () => {
    const onHide = vi.fn()
    const onClose = vi.fn()
    render(
      <NodeContextMenu
        {...baseProps}
        onClose={onClose}
        onHide={onHide}
        isHidden={false}
      />,
    )
    await userEvent.click(
      screen.getByRole('menuitemcheckbox', { name: /Hide Node node-42/i }),
    )
    expect(onHide).toHaveBeenCalledTimes(1)
    expect(onHide).toHaveBeenCalledWith('node-42')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders Expand, Pin, Hide, Isolate, Delete in that order when all handlers are wired', () => {
    render(
      <NodeContextMenu
        {...baseProps}
        onExpand={vi.fn()}
        onPin={vi.fn()}
        onHide={vi.fn()}
        onIsolateNeighborhood={vi.fn()}
        onDelete={vi.fn()}
      />,
    )
    const items = [
      ...screen.getAllByRole('menuitem'),
      ...screen.getAllByRole('menuitemcheckbox'),
    ]
    // Sort by DOM order so the assertion still verifies visual order
    items.sort((a, b) =>
      a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    )
    expect(items.map((b) => b.textContent)).toEqual([
      'Expand Neighborhood',
      'Pin Node',
      'Hide Node',
      'Show only this & its neighbourhood',
      'Delete Node',
    ])
  })
})

describe('NodeContextMenu — Isolate neighbourhood (ROADMAP A11.3)', () => {
  const baseProps = {
    x: 100,
    y: 100,
    nodeId: 'node-7',
    onClose: vi.fn(),
  }

  it('renders the Show only this & its neighbourhood entry when onIsolateNeighborhood is provided', () => {
    render(
      <NodeContextMenu {...baseProps} onIsolateNeighborhood={vi.fn()} />,
    )
    const btn = screen.getByRole('menuitem', {
      name: /Show only node node-7 and its neighbourhood/i,
    })
    expect(btn).toBeInTheDocument()
    expect(btn.textContent).toBe('Show only this & its neighbourhood')
  })

  it('omits the Isolate entry when no handler is provided', () => {
    render(<NodeContextMenu {...baseProps} onExpand={vi.fn()} />)
    expect(
      screen.queryByRole('menuitem', { name: /Show only node/i }),
    ).toBeNull()
  })

  it('invokes onIsolateNeighborhood with the nodeId and closes the menu', async () => {
    const onIsolateNeighborhood = vi.fn()
    const onClose = vi.fn()
    render(
      <NodeContextMenu
        {...baseProps}
        onClose={onClose}
        onIsolateNeighborhood={onIsolateNeighborhood}
      />,
    )
    await userEvent.click(
      screen.getByRole('menuitem', {
        name: /Show only node node-7 and its neighbourhood/i,
      }),
    )
    expect(onIsolateNeighborhood).toHaveBeenCalledTimes(1)
    expect(onIsolateNeighborhood).toHaveBeenCalledWith('node-7')
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
