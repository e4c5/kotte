/**
 * Query execution API.
 */

import apiClient from './api'

export interface QueryExecuteRequest {
  graph: string
  cypher: string
  params?: Record<string, unknown>
  options?: Record<string, unknown>
}

export interface QueryResultRow {
  data: Record<string, unknown>
}

export interface QueryExecuteResponse {
  columns: string[]
  rows: QueryResultRow[]
  row_count: number
  command?: string
  stats?: Record<string, unknown>
  request_id: string
  graph_elements?: {
    nodes: Array<{
      id: string
      label: string
      properties: Record<string, unknown>
      type: string
    }>
    edges: Array<{
      id: string
      label: string
      source: string
      target: string
      properties: Record<string, unknown>
      type: string
    }>
  }
}

export interface QueryCancelResponse {
  cancelled: boolean
  request_id: string
}

export const queryAPI = {
  execute: async (request: QueryExecuteRequest): Promise<QueryExecuteResponse> => {
    const response = await apiClient.post<QueryExecuteResponse>(
      '/queries/execute',
      request
    )
    return response.data
  },

  cancel: async (requestId: string, reason?: string): Promise<QueryCancelResponse> => {
    const response = await apiClient.post<QueryCancelResponse>(
      `/queries/${requestId}/cancel`,
      { reason }
    )
    return response.data
  },
}

