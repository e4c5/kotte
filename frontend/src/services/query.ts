/**
 * Query execution API.
 */

import apiClient, { ensureCsrfToken } from './api'

export interface QueryTemplateParamSchema {
  type: 'integer' | 'string' | 'number'
  default?: unknown
  description?: string
}

export interface QueryTemplate {
  id: string
  name: string
  description: string
  cypher: string
  params: Record<string, unknown>
  param_schema: Record<string, QueryTemplateParamSchema>
}

export interface QueryExecuteRequest {
  graph: string
  cypher: string
  params?: Record<string, unknown>
  options?: Record<string, unknown>
  for_visualization?: boolean
  mutation_confirmed?: boolean
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
    paths?: Array<{
      type: string
      node_ids?: string[]
      edge_ids?: string[]
      segments?: unknown[]
    }>
  }
  visualization_warning?: string
}

export interface QueryCancelResponse {
  cancelled: boolean
  request_id: string
}

export interface QueryStreamRequest {
  graph: string
  cypher: string
  params?: Record<string, unknown>
  chunk_size?: number
  offset?: number
}

export interface QueryStreamChunk {
  columns: string[]
  rows: QueryResultRow[]
  chunk_size: number
  offset: number
  has_more: boolean
  total_rows?: number | null
}

export const queryAPI = {
  listTemplates: async (): Promise<QueryTemplate[]> => {
    const response = await apiClient.get<QueryTemplate[]>('/queries/templates')
    return response.data
  },

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

  stream: async function* (
    request: QueryStreamRequest,
    signal?: AbortSignal
  ): AsyncGenerator<QueryStreamChunk, void, unknown> {
    const csrfToken = (await ensureCsrfToken()) || sessionStorage.getItem('csrf_token') || ''
    const response = await fetch('/api/v1/queries/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
      credentials: 'include',
      body: JSON.stringify(request),
      signal,
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error?.message || 'Streaming failed')
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Response body is not readable')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        if (signal?.aborted) break
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim()) {
            try {
              const chunk = JSON.parse(line) as QueryStreamChunk
              yield chunk
            } catch (e) {
              console.error('Failed to parse chunk:', e, line)
            }
          }
        }
      }

      // Process remaining buffer
      if (buffer.trim() && !signal?.aborted) {
        try {
          const chunk = JSON.parse(buffer) as QueryStreamChunk
          yield chunk
        } catch (e) {
          console.error('Failed to parse final chunk:', e)
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
}
