import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import GraphControls from '../GraphControls'

// Mock the graph store
vi.mock('../stores/graphStore', () => ({
  useGraphStore: () => ({
    layout: 'force',
    setLayout: vi.fn(),
    nodeStyles: {},
    edgeStyles: {},
    setNodeStyle: vi.fn(),
    setEdgeStyle: vi.fn(),
    edgeWidthMapping: { enabled: false },
    setEdgeWidthMapping: vi.fn(),
    filters: {
      nodeLabels: new Set(),
      edgeLabels: new Set(),
      propertyFilters: [],
    },
    toggleNodeLabel: vi.fn(),
    toggleEdgeLabel: vi.fn(),
    addPropertyFilter: vi.fn(),
    removePropertyFilter: vi.fn(),
    clearFilters: vi.fn(),
    resetStyles: vi.fn(),
  }),
}))

describe('GraphControls', () => {
  const defaultProps = {
    availableNodeLabels: ['Person', 'City'],
    availableEdgeLabels: ['KNOWS', 'LIVES_IN'],
  }

  it('renders with layout tab by default', () => {
    render(<GraphControls {...defaultProps} />)
    expect(screen.getByText('Graph Controls')).toBeInTheDocument()
    expect(screen.getByLabelText('Layout Algorithm')).toBeInTheDocument()
  })

  it('switches tabs', () => {
    render(<GraphControls {...defaultProps} />)

    // Switch to filter tab
    const filterBtn = screen.getByRole('button', { name: /^filter$/i })
    fireEvent.click(filterBtn)
    expect(screen.getByText('Node Labels')).toBeInTheDocument()

    // Switch to style tab
    const styleBtn = screen.getByRole('button', { name: /^style$/i })
    fireEvent.click(styleBtn)
    expect(screen.getByText('Node Styles')).toBeInTheDocument()
  })
})
