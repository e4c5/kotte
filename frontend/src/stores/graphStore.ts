/**
 * Graph visualization state management.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { GraphMetadata } from '../services/graph'

export type LayoutType =
  | 'force'
  | 'hierarchical'
  | 'radial'
  | 'grid'
  | 'random'
  | 'cluster'
  | 'partition'
  | 'pack'

export interface LabelStyle {
  color: string
  size: number
  captionField?: string
  showLabel?: boolean
}

export interface GraphFilters {
  nodeLabels: Set<string>
  edgeLabels: Set<string>
  propertyFilters: Array<{
    id: string
    label?: string
    property: string
    value: string
    operator: 'equals' | 'contains' | 'startsWith' | 'endsWith'
  }>
}

export interface EdgeWidthMapping {
  enabled: boolean
  property: string | null
  scaleType: 'linear' | 'log'
  minWidth: number
  maxWidth: number
}

interface GraphState {
  // Layout
  layout: LayoutType
  setLayout: (layout: LayoutType) => void

  // Styling
  nodeStyles: Record<string, LabelStyle>
  edgeStyles: Record<string, LabelStyle>
  setNodeStyle: (label: string, style: Partial<LabelStyle>) => void
  setEdgeStyle: (label: string, style: Partial<LabelStyle>) => void
  resetStyles: () => void

  // Edge width mapping
  edgeWidthMapping: EdgeWidthMapping
  setEdgeWidthMapping: (mapping: Partial<EdgeWidthMapping>) => void

  // Filtering
  filters: GraphFilters
  toggleNodeLabel: (label: string) => void
  toggleEdgeLabel: (label: string) => void
  addPropertyFilter: (
    filter: Omit<GraphFilters['propertyFilters'][number], 'id'> & { id?: string }
  ) => void
  removePropertyFilter: (filterId: string) => void
  clearFilters: () => void

  // Graph state
  selectedNode: string | null
  setSelectedNode: (nodeId: string | null) => void
  selectedEdge: string | null
  setSelectedEdge: (edgeId: string | null) => void
  pinnedNodes: Set<string>
  togglePinNode: (nodeId: string) => void
  hiddenNodes: Set<string>
  toggleHideNode: (nodeId: string) => void

  // Camera focus (ROADMAP A11 phase 2). Populated by `WorkspacePage` after
  // an additive double-click expand merges new neighbours into the canvas;
  // consumed by `GraphView`, which animates the d3-zoom transform to fit the
  // union {clicked node} ∪ addedNodeIds and then clears the field. Empty
  // array means "no pending focus" — the canvas keeps whatever transform
  // it already has.
  cameraFocusAnchorIds: string[]
  setCameraFocusAnchorIds: (ids: string[]) => void
  clearCameraFocusAnchorIds: () => void

  /** Latest `/graphs/.../metadata` for the sidebar’s current graph (not persisted). */
  graphMetadata: GraphMetadata | null
  setGraphMetadata: (metadata: GraphMetadata | null) => void
}

const defaultNodeStyle: LabelStyle = {
  color: '#1f77b4',
  size: 10,
  captionField: 'label',
  showLabel: true,
}

const defaultEdgeStyle: LabelStyle = {
  color: '#999',
  size: 2,
  captionField: 'label',
  showLabel: true,
}

export const useGraphStore = create<GraphState>()(
  persist(
    (set) => ({
      layout: 'force',
      nodeStyles: {},
      edgeStyles: {},
      edgeWidthMapping: {
        enabled: false,
        property: null,
        scaleType: 'linear',
        minWidth: 1,
        maxWidth: 10,
      },
      filters: {
        nodeLabels: new Set(),
        edgeLabels: new Set(),
        propertyFilters: [],
      },
      selectedNode: null,
      selectedEdge: null,
      pinnedNodes: new Set(),
      hiddenNodes: new Set(),
      cameraFocusAnchorIds: [],
      graphMetadata: null,

      setLayout: (layout) => set({ layout }),

      setGraphMetadata: (metadata) => set({ graphMetadata: metadata }),

      setEdgeWidthMapping: (mapping) =>
        set((state) => ({
          edgeWidthMapping: {
            ...state.edgeWidthMapping,
            ...mapping,
          },
        })),

      setNodeStyle: (label, style) =>
        set((state) => ({
          nodeStyles: {
            ...state.nodeStyles,
            [label]: {
              ...defaultNodeStyle,
              ...state.nodeStyles[label],
              ...style,
            },
          },
        })),

      setEdgeStyle: (label, style) =>
        set((state) => ({
          edgeStyles: {
            ...state.edgeStyles,
            [label]: {
              ...defaultEdgeStyle,
              ...state.edgeStyles[label],
              ...style,
            },
          },
        })),

      resetStyles: () =>
        set({
          nodeStyles: {},
          edgeStyles: {},
        }),

      toggleNodeLabel: (label) =>
        set((state) => {
          const newSet = new Set(state.filters.nodeLabels)
          if (newSet.has(label)) {
            newSet.delete(label)
          } else {
            newSet.add(label)
          }
          return {
            filters: {
              ...state.filters,
              nodeLabels: newSet,
            },
          }
        }),

      toggleEdgeLabel: (label) =>
        set((state) => {
          const newSet = new Set(state.filters.edgeLabels)
          if (newSet.has(label)) {
            newSet.delete(label)
          } else {
            newSet.add(label)
          }
          return {
            filters: {
              ...state.filters,
              edgeLabels: newSet,
            },
          }
        }),

      addPropertyFilter: (filter) =>
        set((state) => ({
          filters: {
            ...state.filters,
            propertyFilters: [
              ...state.filters.propertyFilters,
              { ...filter, id: filter.id ?? crypto.randomUUID() },
            ],
          },
        })),

      removePropertyFilter: (filterId) =>
        set((state) => ({
          filters: {
            ...state.filters,
            propertyFilters: state.filters.propertyFilters.filter(
              (f) => f.id !== filterId
            ),
          },
        })),

      clearFilters: () =>
        set({
          filters: {
            nodeLabels: new Set(),
            edgeLabels: new Set(),
            propertyFilters: [],
          },
        }),

      setSelectedNode: (nodeId) => set({ selectedNode: nodeId, selectedEdge: null }),

      setSelectedEdge: (edgeId) => set({ selectedEdge: edgeId, selectedNode: null }),

      togglePinNode: (nodeId) =>
        set((state) => {
          const newSet = new Set(state.pinnedNodes)
          if (newSet.has(nodeId)) {
            newSet.delete(nodeId)
          } else {
            newSet.add(nodeId)
          }
          return { pinnedNodes: newSet }
        }),

      toggleHideNode: (nodeId) =>
        set((state) => {
          const newSet = new Set(state.hiddenNodes)
          if (newSet.has(nodeId)) {
            newSet.delete(nodeId)
          } else {
            newSet.add(nodeId)
          }
          return { hiddenNodes: newSet }
        }),

      setCameraFocusAnchorIds: (ids) =>
        set({ cameraFocusAnchorIds: Array.from(new Set(ids)) }),

      clearCameraFocusAnchorIds: () =>
        set((state) =>
          state.cameraFocusAnchorIds.length === 0
            ? state
            : { cameraFocusAnchorIds: [] },
        ),
    }),
    {
      name: 'kotte-graph-styles',
      partialize: (state) => ({
        nodeStyles: state.nodeStyles,
        edgeStyles: state.edgeStyles,
        layout: state.layout,
      }),
    }
  )
)
