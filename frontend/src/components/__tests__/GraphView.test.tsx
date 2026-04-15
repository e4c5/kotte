import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import GraphView, { type GraphNode, type GraphEdge } from '../GraphView'

vi.mock('d3', async (importOriginal) => {
  const actual = await importOriginal<typeof import('d3')>()
  
  const createMockSelection = () => {
    const simulation: any = {
      alpha: vi.fn(),
      alphaDecay: vi.fn(),
      velocityDecay: vi.fn(),
      force: vi.fn(),
      on: vi.fn(),
      stop: vi.fn(),
      tick: vi.fn(),
      alphaTarget: vi.fn(),
      restart: vi.fn(),
      nodes: vi.fn(),
    }

    const forceObj = {
      id: vi.fn().mockReturnThis(),
      distance: vi.fn().mockReturnThis(),
      strength: vi.fn().mockReturnThis(),
      radius: vi.fn().mockReturnThis(),
      links: vi.fn().mockReturnThis(),
    }

    simulation.alpha.mockReturnThis()
    simulation.alphaDecay.mockReturnThis()
    simulation.velocityDecay.mockReturnThis()
    simulation.force.mockImplementation((_name: string, arg?: any) => {
      if (arg === undefined) return forceObj
      return simulation
    })
    simulation.on.mockReturnThis()
    simulation.stop.mockReturnThis()
    simulation.tick.mockReturnThis()
    simulation.alphaTarget.mockReturnThis()
    simulation.restart.mockReturnThis()
    simulation.nodes.mockReturnThis()

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

    return { selection, simulation }
  }

  const { selection: mockSelection, simulation: mockSimulation } = createMockSelection()
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
    forceSimulation: vi.fn().mockReturnValue(mockSimulation),
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
