import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import GraphView, { type GraphNode, type GraphEdge } from '../GraphView'

vi.mock('d3', async (importOriginal) => {
  const actual = await importOriginal<typeof import('d3')>()
  
  const createMockSelection = () => {
    const selection: any = {
      selectAll: vi.fn(),
      remove: vi.fn(),
      append: vi.fn(),
      attr: vi.fn(),
      style: vi.fn(),
      on: vi.fn(),
      call: vi.fn(),
      text: vi.fn(),
      data: vi.fn(),
      enter: vi.fn(),
      exit: vi.fn(),
      node: vi.fn(),
      transition: vi.fn(),
      duration: vi.fn(),
      styleTo: vi.fn(),
      tick: vi.fn(),
    }

    selection.selectAll.mockReturnValue(selection)
    selection.remove.mockReturnValue(selection)
    selection.append.mockReturnValue(selection)
    selection.attr.mockReturnValue(selection)
    selection.style.mockReturnValue(selection)
    selection.on.mockReturnValue(selection)
    selection.call.mockReturnValue(selection)
    selection.text.mockReturnValue(selection)
    selection.data.mockReturnValue(selection)
    selection.enter.mockReturnValue(selection)
    selection.exit.mockReturnValue(selection)
    selection.node.mockReturnValue({})
    selection.transition.mockReturnValue(selection)
    selection.duration.mockReturnValue(selection)
    selection.tick.mockReturnValue(selection)

    return selection
  }

  const mockSelection = createMockSelection()
  return {
    ...actual,
    select: vi.fn().mockReturnValue(mockSelection),
    zoom: vi.fn().mockReturnValue({
      scaleExtent: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
      transform: vi.fn().mockReturnThis(),
      scaleTo: vi.fn().mockReturnThis(),
    }),
    zoomIdentity: {
      translate: vi.fn().mockReturnThis(),
      scale: vi.fn().mockReturnThis(),
    },
    forceSimulation: vi.fn().mockReturnValue({
      alpha: vi.fn().mockReturnThis(),
      alphaDecay: vi.fn().mockReturnThis(),
      velocityDecay: vi.fn().mockReturnThis(),
      force: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
      stop: vi.fn().mockReturnThis(),
      tick: vi.fn().mockReturnThis(),
    }),
    drag: vi.fn().mockReturnValue({
      on: vi.fn().mockReturnThis(),
    }),
    scaleOrdinal: vi.fn().mockReturnValue(vi.fn().mockReturnValue('#999')),
    schemeCategory10: [],
  }
})

describe('GraphView', () => {
  const mockNodes: GraphNode[] = [
    { id: '1', label: 'Person', properties: { name: 'Alice' } },
    { id: '2', label: 'Person', properties: { name: 'Bob' } },
  ]
  const mockEdges: GraphEdge[] = [
    { id: 'e1', label: 'KNOWS', source: '1', target: '2', properties: {} },
  ]

  it('renders without crashing', () => {
    const { container } = render(
      <GraphView nodes={mockNodes} edges={mockEdges} />
    )
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('shows debug marker', () => {
    const { getByText } = render(
      <GraphView nodes={mockNodes} edges={mockEdges} />
    )
    expect(getByText(/GraphView marker/)).toBeInTheDocument()
  })
})
