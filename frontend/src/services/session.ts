/**
 * Session management API.
 */

import apiClient from './api'

export interface ConnectionConfig {
  host: string
  port: number
  database: string
  user: string
  password: string
  sslmode?: string
}

export interface ConnectRequest {
  connection: ConnectionConfig
}

export interface ConnectResponse {
  session_id: string
  connected: boolean
  database: string
  host: string
  port: number
}

export interface SessionStatus {
  connected: boolean
  database?: string
  host?: string
  port?: number
  current_graph?: string
}

export const sessionAPI = {
  connect: async (config: ConnectionConfig): Promise<ConnectResponse> => {
    const response = await apiClient.post<ConnectResponse>('/session/connect', {
      connection: config,
    })
    return response.data
  },

  disconnect: async (): Promise<void> => {
    await apiClient.post('/session/disconnect')
  },

  getStatus: async (): Promise<SessionStatus> => {
    const response = await apiClient.get<SessionStatus>('/session/status')
    return response.data
  },
}

