/**
 * Graph metadata API.
 */

import apiClient from './api'

export interface GraphInfo {
  name: string
  id?: string
}

export interface NodeLabel {
  label: string
  count: number
  properties: string[]
}

export interface EdgeLabel {
  label: string
  count: number
  properties: string[]
}

export interface GraphMetadata {
  graph_name: string
  node_labels: NodeLabel[]
  edge_labels: EdgeLabel[]
  role?: string
}

export interface MetaGraphEdge {
  source_label: string
  target_label: string
  edge_label: string
  count: number
}

export interface MetaGraphResponse {
  graph_name: string
  relationships: MetaGraphEdge[]
}

export interface NodeExpandRequest {
  depth?: number
  limit?: number
}

export interface GraphNode {
  id: string
  label: string
  properties: Record<string, unknown>
  type: string
}

export interface GraphEdge {
  id: string
  label: string
  source: string
  target: string
  properties: Record<string, unknown>
  type: string
}

export interface NodeExpandResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  node_count: number
  edge_count: number
}

export const graphAPI = {
  listGraphs: async (): Promise<GraphInfo[]> => {
    const response = await apiClient.get<GraphInfo[]>('/graphs')
    return response.data
  },

  getMetadata: async (graphName: string): Promise<GraphMetadata> => {
    const response = await apiClient.get<GraphMetadata>(
      `/graphs/${encodeURIComponent(graphName)}/metadata`
    )
    return response.data
  },

  getMetaGraph: async (graphName: string): Promise<MetaGraphResponse> => {
    const response = await apiClient.get<MetaGraphResponse>(
      `/graphs/${encodeURIComponent(graphName)}/meta-graph`
    )
    return response.data
  },

  expandNode: async (
    graphName: string,
    nodeId: string,
    request: NodeExpandRequest = {}
  ): Promise<NodeExpandResponse> => {
    const response = await apiClient.post<NodeExpandResponse>(
      `/graphs/${encodeURIComponent(graphName)}/nodes/${encodeURIComponent(nodeId)}/expand`,
      request
    )
    return response.data
  },
}

