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

export interface PropertyStatistics {
  property: string
  min: number | null
  max: number | null
}

export interface EdgeLabel {
  label: string
  count: number
  properties: string[]
  property_statistics?: PropertyStatistics[]
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

export interface NodeDeleteRequest {
  detach?: boolean
}

export interface NodeDeleteResponse {
  deleted: boolean
  node_id: string
  edges_deleted: number
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

  deleteNode: async (
    graphName: string,
    nodeId: string,
    request: NodeDeleteRequest = {}
  ): Promise<NodeDeleteResponse> => {
    // Use query params for the detach option (FastAPI DELETE endpoints accept query params)
    const params = new URLSearchParams()
    if (request.detach !== undefined) {
      params.append('detach', String(request.detach))
    }
    const url = `/graphs/${encodeURIComponent(graphName)}/nodes/${encodeURIComponent(nodeId)}`
    const response = await apiClient.delete<NodeDeleteResponse>(
      params.toString() ? `${url}?${params.toString()}` : url
    )
    return response.data
  },
}

