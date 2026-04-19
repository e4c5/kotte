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
    const btn = screen.getByRole('menuitem', { name: /Pin Node node-42/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders Unpin Node when isPinned=true', () => {
    render(<NodeContextMenu {...baseProps} onPin={vi.fn()} isPinned={true} />)
    const btn = screen.getByRole('menuitem', { name: /Unpin Node node-42/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('renders Hide Node when onHide is provided and node is not hidden', () => {
    render(<NodeContextMenu {...baseProps} onHide={vi.fn()} isHidden={false} />)
    expect(screen.getByRole('menuitem', { name: /Hide Node node-42/i })).toBeInTheDocument()
  })

  it('renders Show Node when isHidden=true', () => {
    render(<NodeContextMenu {...baseProps} onHide={vi.fn()} isHidden={true} />)
    expect(screen.getByRole('menuitem', { name: /Show Node node-42/i })).toBeInTheDocument()
  })

  it('omits Pin/Hide buttons when handlers are not provided', () => {
    render(<NodeContextMenu {...baseProps} onExpand={vi.fn()} />)
    expect(screen.queryByRole('menuitem', { name: /Pin Node/i })).toBeNull()
    expect(screen.queryByRole('menuitem', { name: /Hide Node/i })).toBeNull()
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
    await userEvent.click(screen.getByRole('menuitem', { name: /Pin Node node-42/i }))
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
    await userEvent.click(screen.getByRole('menuitem', { name: /Hide Node node-42/i }))
    expect(onHide).toHaveBeenCalledTimes(1)
    expect(onHide).toHaveBeenCalledWith('node-42')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders Expand, Pin, Hide, Delete in that order when all handlers are wired', () => {
    render(
      <NodeContextMenu
        {...baseProps}
        onExpand={vi.fn()}
        onPin={vi.fn()}
        onHide={vi.fn()}
        onDelete={vi.fn()}
      />,
    )
    const items = screen.getAllByRole('menuitem')
    expect(items.map((b) => b.textContent)).toEqual([
      'Expand Neighborhood',
      'Pin Node',
      'Hide Node',
      'Delete Node',
    ])
  })
})
